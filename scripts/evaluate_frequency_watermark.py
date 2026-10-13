"""Build a private, offline comparison gallery for frequency signature experiments."""

from __future__ import annotations

import argparse
import json
import secrets
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
from frequency_watermark_core import (
    VERSION,
    Spec,
    embed,
    extract,
    image_metrics,
    luminance,
    recovery_metrics,
    signature_bits,
)
from frequency_watermark_demo import digest, load_rgb, save_bitmap, save_jpeg, write_json
from PIL import Image, ImageDraw, ImageFont

from aim_tool.services.images import prepare_jpeg
from aim_tool.services.resources import local_project_resources
from aim_tool.services.watermark import (
    WatermarkConfig,
    composite_watermark,
    render_watermark_region,
)

LEVELS = {"dct": {"low": 8, "medium": 16, "high": 32}, "fft": {"low": 10, "medium": 20, "high": 40}}


def png(path: Path, image: Image.Image) -> None:
    with path.open("xb") as stream:
        image.save(stream, format="PNG")


def roi_boxes(rgb: np.ndarray) -> dict[str, tuple[int, int, int, int]]:
    """Choose smooth, detailed and dark patches on a fixed interior grid."""
    h, w = rgb.shape[:2]
    size = min(512, w, h)
    y = luminance(rgb)
    candidates = []
    for fy in np.linspace(0.15, 0.88, 6):
        for fx in np.linspace(0.15, 0.85, 7):
            x0 = int(np.clip(round(w * fx - size / 2), 0, w - size))
            y0 = int(np.clip(round(h * fy - size / 2), 0, h - size))
            crop = y[y0 : y0 + size, x0 : x0 + size]
            gradient = float(np.abs(np.diff(crop, axis=1)).mean())
            candidates.append(
                (float(crop.std()), gradient, float(crop.mean()), (x0, y0, x0 + size, y0 + size))
            )
    return {
        "smooth": min(candidates, key=lambda c: c[0])[3],
        "detail": max(candidates, key=lambda c: c[1])[3],
        "shadow": min(candidates, key=lambda c: c[2])[3],
    }


def previews(
    directory: Path, name: str, rgb: np.ndarray, boxes: dict, baseline: np.ndarray | None = None
) -> None:
    image = Image.fromarray(rgb)
    small = image.copy()
    small.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
    png(directory / f"{name}-overview.png", small)
    for kind, box in boxes.items():
        crop = image.crop(box)
        png(directory / f"{name}-{kind}.png", crop)
        if baseline is not None:
            x0, y0, x1, y1 = box
            difference = np.abs(
                rgb[y0:y1, x0:x1].astype(np.int16) - baseline[y0:y1, x0:x1].astype(np.int16)
            )
            png(
                directory / f"{name}-{kind}-diff.png",
                Image.fromarray(np.clip(difference * 16, 0, 255).astype(np.uint8)),
            )


def read_and_score(path: Path, spec: Spec, key: str, bits: np.ndarray) -> tuple[dict, np.ndarray]:
    recovered = extract(load_rgb(path), spec, key)
    return recovery_metrics(bits, recovered), recovered


def attacks(directory: Path, name: str, prepared, rgb, spec, key, bits) -> dict:
    result = {}
    for quality in (90, 75, 50):
        suffix = f"jpeg_q{quality}"
        path = directory / f"{name}-{suffix}.jpg"
        # Typical 4:2:0 recompression, unlike the original 4:4:4 Q95 export.
        save_jpeg(path, rgb, prepared, quality=quality, subsampling=2)
        metrics, recovered = read_and_score(path, spec, key, bits)
        save_bitmap(directory / f"{name}-{suffix}-signature.png", recovered)
        result[suffix] = {**metrics, "alignment": "none; same dimensions"}
    w, h = spec.image_size
    resized = Image.fromarray(rgb).resize((w // 2, h // 2), Image.Resampling.LANCZOS)
    path = directory / f"{name}-half-size.jpg"
    save_jpeg(path, np.asarray(resized), prepared, quality=90, subsampling=2)
    half = load_rgb(path)
    try:
        extract(half, spec, key)
    except ValueError:
        result["half_size_direct"] = {"supported": False, "reason": "no geometry synchronization"}
    else:
        raise AssertionError("Wrong-size extraction unexpectedly succeeded")
    restored = np.asarray(Image.fromarray(half).resize(spec.image_size, Image.Resampling.LANCZOS))
    recovered = extract(restored, spec, key)
    save_bitmap(directory / f"{name}-half-size-assisted-signature.png", recovered)
    result["half_size_assisted"] = {
        **recovery_metrics(bits, recovered),
        "alignment": "known original dimensions; upscale 2x",
    }
    # Remove 5% from each edge. No crop origin is inferred by the algorithm.
    left, top = round(w * 0.05), round(h * 0.05)
    cropped = rgb[top : h - top, left : w - left]
    path = directory / f"{name}-crop90.jpg"
    save_jpeg(path, cropped, prepared, quality=90, subsampling=2)
    crop_rgb = load_rgb(path)
    try:
        extract(crop_rgb, spec, key)
    except ValueError:
        result["crop90_direct"] = {"supported": False, "reason": "no geometry synchronization"}
    else:
        raise AssertionError("Wrong-size extraction unexpectedly succeeded")
    canvas = np.full_like(rgb, 128)
    canvas[top : h - top, left : w - left] = crop_rgb
    recovered = extract(canvas, spec, key)
    save_bitmap(directory / f"{name}-crop90-assisted-signature.png", recovered)
    result["crop90_assisted"] = {
        **recovery_metrics(bits, recovered),
        "alignment": "known crop offset and original dimensions; missing pixels filled with 128",
    }
    return result


def evaluate_source(source: Path, root: Path, index: int, bits: np.ndarray, key: str) -> dict:
    directory = root / f"sample-{index}"
    directory.mkdir()
    prepared = prepare_jpeg(source)
    original = np.asarray(prepared.pixels)
    boxes = roi_boxes(original)
    save_jpeg(directory / "baseline.jpg", original, prepared)
    baseline = load_rgb(directory / "baseline.jpg")
    previews(directory, "original", original, boxes)
    previews(directory, "baseline", baseline, boxes)
    print(f"sample-{index}: baseline ready", flush=True)
    rows = []
    for algorithm, levels in LEVELS.items():
        for level, strength in levels.items():
            name = f"{algorithm}-{level}"
            spec = Spec(algorithm, prepared.pixels.size, bits.shape[::-1], strength)
            start = time.perf_counter()
            marked, stats = embed(original, bits, spec, key)
            embed_seconds = time.perf_counter() - start
            before_encoding = image_metrics(original, marked)
            path = directory / f"{name}.jpg"
            save_jpeg(path, marked, prepared)
            del marked
            reopened = load_rgb(path)
            start = time.perf_counter()
            recovered = extract(reopened, spec, key)
            extract_seconds = time.perf_counter() - start
            recovery = recovery_metrics(bits, recovered)
            save_bitmap(directory / f"{name}-signature.png", recovered)
            negatives = {}
            for label, pixels, candidate_key in (
                ("unmarked", baseline, key),
                ("wrong_key", reopened, key + "wrong"),
            ):
                result = extract(pixels, spec, candidate_key)
                negatives[label] = recovery_metrics(bits, result)
                save_bitmap(directory / f"{name}-{label}-signature.png", result)
            previews(directory, name, reopened, boxes, baseline)
            row = {
                "name": name,
                "algorithm": algorithm,
                "level": level,
                "strength": strength,
                "spec": spec.to_dict(),
                "embedding": {**stats, "seconds": embed_seconds, "quality": before_encoding},
                "extract_seconds": extract_seconds,
                "bytes": path.stat().st_size,
                "versus_original": image_metrics(original, reopened),
                "versus_baseline": image_metrics(baseline, reopened),
                "recovery": recovery,
                "negatives": negatives,
                "attacks": attacks(directory, name, prepared, reopened, spec, key, bits),
            }
            rows.append(row)
            write_json(directory / f"{name}.json", {"spec": spec.to_dict(), "key": key})
            write_json(directory / f"{name}-metrics.json", row)
            print(
                f"sample-{index}: {name} BER={recovery['ber']:.4%}, "
                f"PSNR(base)={row['versus_baseline']['psnr_rgb_db']:.2f}, "
                f"Q75 BER={row['attacks']['jpeg_q75']['ber']:.4%}",
                flush=True,
            )
    return {
        "id": f"sample-{index}",
        "source": str(source.resolve()),
        "size": prepared.pixels.size,
        "warnings": prepared.warnings,
        "roi_boxes": boxes,
        "baseline_bytes": (directory / "baseline.jpg").stat().st_size,
        "baseline_versus_original": image_metrics(original, baseline),
        "cases": rows,
    }


def select_case(samples: list[dict]) -> tuple[str, str]:
    names = [row["name"] for row in samples[0]["cases"]]
    candidates = {
        name: [next(r for r in s["cases"] if r["name"] == name) for s in samples] for name in names
    }
    eligible = [
        name
        for name, rows in candidates.items()
        if all(
            row["recovery"]["exact"] and row["attacks"]["jpeg_q75"]["ber"] <= 0.01 for row in rows
        )
    ]
    if eligible:
        best = max(
            eligible,
            key=lambda n: np.mean([r["versus_baseline"]["psnr_rgb_db"] for r in candidates[n]]),
        )
        reason = "两张样图首次保存精确恢复且 Q75 误码率 <=1% 的方案中，取平均基线 PSNR 最高者"
    else:
        best = min(
            names,
            key=lambda n: np.mean(
                [r["recovery"]["ber"] + r["attacks"]["jpeg_q75"]["ber"] for r in candidates[n]]
            ),
        )
        reason = "无方案满足预设条件；取首次保存与 Q75 平均误码率最低者，仅作探索"
    return best, reason


def combination(
    source: Path, root: Path, sample: dict, name: str, bits: np.ndarray, key: str, resources
) -> dict:
    directory = root / sample["id"]
    prepared = prepare_jpeg(source)
    config = WatermarkConfig(
        category="landscape", content="频域水印 Demo", taken_on=date(2026, 10, 13)
    )
    region = render_watermark_region(prepared.pixels.size, config, resources)
    composite_watermark(prepared.pixels, region)
    visible = np.asarray(prepared.pixels)
    save_jpeg(directory / "visible-only.jpg", visible, prepared)
    baseline = load_rgb(directory / "visible-only.jpg")
    selected = next(r for r in sample["cases"] if r["name"] == name)
    spec = Spec.from_dict(selected["spec"])
    marked, stats = embed(visible, bits, spec, key)
    save_jpeg(directory / "combined.jpg", marked, prepared)
    reopened = load_rgb(directory / "combined.jpg")
    recovered = extract(reopened, spec, key)
    save_bitmap(directory / "combined-signature.png", recovered)
    boxes = dict(sample["roi_boxes"])
    x0, y0, x1, y1 = region.bounds
    crop_size = min(512, *prepared.pixels.size)
    left = max(0, min(x1 - crop_size, prepared.pixels.width - crop_size))
    top = max(0, min(y1 - crop_size, prepared.pixels.height - crop_size))
    boxes["visible"] = (left, top, left + crop_size, top + crop_size)
    previews(directory, "visible-only", baseline, boxes)
    previews(directory, "combined", reopened, boxes, baseline)
    write_json(directory / "combined.json", {"spec": spec.to_dict(), "key": key})
    return {
        "name": name,
        "recovery": recovery_metrics(bits, recovered),
        "versus_visible_only": image_metrics(baseline, reopened),
        "embedding": stats,
        "visible_bounds": (x0, y0, x1, y1),
    }


def gallery(root: Path, report: dict) -> None:
    # Embedded JSON has only local relative gallery paths and measured values.
    data = json.dumps(
        {"samples": report["samples"], "selected": report["selected"]}, ensure_ascii=False
    ).replace("<", "\\u003c")
    page = r"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>频域签名水印 · 本地实验</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10151d;color:#e8edf5;font:15px/1.6 system-ui,sans-serif}
main{max-width:1500px;margin:auto;padding:28px}h1{font-size:28px;margin:0 0 8px}p{color:#bbc9da}
.controls{display:flex;flex-wrap:wrap;gap:14px;padding:16px;background:#1c2533;border-radius:12px}
label{display:flex;gap:8px;align-items:center}select,button{padding:8px;background:#26364a;color:white;
border:1px solid #547091;border-radius:6px}button{cursor:pointer}.panel{margin-top:22px}
.cards{display:flex;flex-wrap:wrap;gap:10px}.card{background:#1c2533;padding:12px;border-radius:8px}
.frame{overflow:auto;background:#080b10;border:1px solid #37485f;position:relative}
.stage{position:relative;margin:auto;width:max-content;line-height:0}.stage img{display:block}
#overlay{position:absolute;left:0;top:0;overflow:hidden;height:100%;width:50%}
#divider{position:absolute;left:50%;top:0;bottom:0;border-left:2px solid #fdcc70;pointer-events:none}
.signature{display:flex;gap:20px;flex-wrap:wrap;background:#1c2533;padding:16px}
.signature img{max-width:100%;image-rendering:pixelated;display:block;background:white}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px;border-bottom:1px solid #354357}
a{color:#8cc6ff}.note{background:#213046;border-left:3px solid #fdcc70;padding:12px}
#diff{max-width:100%}#quality{font-size:14px}.table-wrap{overflow:auto}
</style><main><h1>频域签名水印 · 画质与恢复</h1>
<p>本地照片实测。先查看全图，再切换 100% 局部；黄色分界左侧为候选、右侧为参考。
Q95 / 4:4:4 导出。全部指标基于完整图像，缩略预览仅帮助浏览。</p>
<div class="controls">
<label>样图 <select id="sample"></select></label><label>候选 <select id="case"></select></label>
<label>视图 <select id="view"><option value="overview">全图概览</option><option value="smooth">平滑区域 · 100%</option>
<option value="detail">细节区域 · 100%</option><option value="shadow">暗部区域 · 100%</option>
<option value="visible">可见水印 · 100%</option></select></label>
<label>参考 <select id="reference"><option value="baseline">同参数编码基线</option>
<option value="original">原始解码像素</option></select></label>
<label>分界 <input id="slider" aria-label="图像分界位置" type="range" min="0" max="100" value="50"></label>
<button id="toggle">查看候选全幅</button></div>
<div class="panel cards" id="quality"></div>
<div class="panel frame"><div class="stage" id="stage"><img id="base" alt="参考图">
<div id="overlay"><img id="candidate" alt="频域水印候选"></div><div id="divider"></div></div></div>
<p id="caption"></p><div class="panel"><h3>签名提取</h3><label>提取条件 <select id="attack">
<option value="saved">首次保存 Q95</option><option value="jpeg_q90">重压缩 Q90 / 4:2:0</option>
<option value="jpeg_q75">重压缩 Q75 / 4:2:0</option><option value="jpeg_q50">重压缩 Q50 / 4:2:0</option>
<option value="half_size_assisted">缩至 50% 后按已知原尺寸恢复</option>
<option value="crop90_assisted">保留中心 90% 后按已知裁剪位置恢复</option>
<option value="unmarked">负例：未嵌入图片</option><option value="wrong_key">负例：错误密钥</option></select></label>
<p id="recovery"></p><div class="signature"><div>实际嵌入笔画<img src="signature-embedded.png" alt="嵌入签名"></div>
<div>提取结果<img id="extracted" alt="恢复签名"></div></div></div>
<div class="panel"><h3>局部差异 ×16</h3><p>候选与同参数基线的 RGB 绝对差放大 16 倍；黑色表示无差异。
这张图用于定位变化，不表示正常查看时的视觉效果。全图视图下显示平滑区域差异。</p><img id="diff" alt="差异增强图"></div>
<div class="panel"><h3>完整图像测量</h3><div class="table-wrap"><table><thead><tr>
<th>候选</th><th>基线 PSNR / dB</th><th>基线 Y-SSIM</th><th>首次 BER</th><th>Q75 BER</th>
<th>嵌入 / 秒</th><th>提取 / 秒</th><th>大小 / MiB</th></tr></thead><tbody id="rows"></tbody></table></div></div>
<p class="note">缩放、裁剪的直接提取均不支持自动几何同步；此处辅助结果使用已知原尺寸或裁剪位置。
负例指标只用于检查本次试验，尚无认证检测器或经校准的误报阈值。实验文件不保留完整拍摄 EXIF/GPS。</p>
<p><a href="report.json">完整本地结果 JSON</a> · <a id="download">下载当前完整 JPG</a></p>
</main><script>const DATA=__DATA__;
const $=id=>document.getElementById(id);const pct=n=>(n*100).toFixed(3)+'%';
const f=n=>n==null?'∞':n.toFixed(3);let active;
DATA.samples.forEach((s,i)=>$('sample').add(new Option('样图 '+(i+1)+' · '+s.size.join(' × '),i)));
function refreshCases(){const s=DATA.samples[+$('sample').value];$('case').innerHTML='';
s.cases.forEach(c=>$('case').add(new Option(c.algorithm.toUpperCase()+' · '+({low:'低',medium:'中',high:'高'}[c.level]),c.name)));
if(s.combination)$('case').add(new Option('可见水印 + '+DATA.selected,'combined'));
$('case').value=DATA.selected;render();}
function divider(){const v=$('slider').value;$('overlay').style.width=v+'%';$('divider').style.left=v+'%';}
function render(){const s=DATA.samples[+$('sample').value],name=$('case').value,combo=name==='combined';
active=s.cases.find(c=>c.name===(combo?DATA.selected:name));const dir=s.id+'/',view=$('view').value;
const actualView=view==='visible'&&!combo?'detail':view,ref=combo?'visible-only':$('reference').value;
$('reference').disabled=combo;$('base').src=dir+ref+'-'+actualView+'.png';
$('candidate').src=dir+name+'-'+actualView+'.png';
$('stage').style.width=actualView==='overview'?'100%':'max-content';
$('base').style.width=actualView==='overview'?'100%':'auto';
$('candidate').style.width=actualView==='overview'?$('stage').clientWidth+'px':'auto';
const metrics=combo?s.combination.versus_visible_only:active.versus_baseline;
$('quality').innerHTML=['基线 PSNR '+f(metrics.psnr_rgb_db)+' dB','基线 Y-SSIM '+f(metrics.ssim_y),
'原图 PSNR '+(combo?'见组合对照':f(active.versus_original.psnr_rgb_db)+' dB'),
'基线编码 PSNR '+f(s.baseline_versus_original.psnr_rgb_db)+' dB'].map(x=>'<div class="card">'+x+'</div>').join('');
$('caption').textContent=(actualView==='overview'?'概览经过缩小；局部视图为原始像素 1:1。':
'100% 局部：图像按原始像素 1:1 显示，可横向滚动。')+' 左：候选；右：'+(combo?'仅可见水印':ref==='baseline'?'编码基线':'原始像素');
$('diff').src=dir+name+'-'+(actualView==='overview'?'smooth':actualView)+'-diff.png';
$('download').href=dir+name+'.jpg';$('download').download=name+'.jpg';
$('rows').innerHTML=s.cases.map(c=>'<tr><td>'+c.name+'</td><td>'+f(c.versus_baseline.psnr_rgb_db)+
'</td><td>'+c.versus_baseline.ssim_y.toFixed(6)+'</td><td>'+pct(c.recovery.ber)+'</td><td>'+pct(c.attacks.jpeg_q75.ber)+
'</td><td>'+f(c.embedding.seconds)+'</td><td>'+f(c.extract_seconds)+'</td><td>'+(c.bytes/1048576).toFixed(2)+'</td></tr>').join('');
$('attack').disabled=combo;recovery();divider();}
function recovery(){const s=DATA.samples[+$('sample').value],name=$('case').value,a=$('attack').value;
let m,path;if(name==='combined'){m=s.combination.recovery;path='combined-signature.png';}
else if(a==='saved'){m=active.recovery;path=name+'-signature.png';}
else if(a==='unmarked'||a==='wrong_key'){m=active.negatives[a];path=name+'-'+a+'-signature.png';}
else{m=active.attacks[a];const suffix=a==='half_size_assisted'?'half-size-assisted':a==='crop90_assisted'?'crop90-assisted':a;
path=name+'-'+suffix+'-signature.png';}
$('extracted').src=s.id+'/'+path;$('recovery').textContent='误码率 '+pct(m.ber)+' · 笔画召回 '+pct(m.stroke_recall)+
' · 笔画精确率 '+pct(m.stroke_precision)+' · 笔画 IoU '+pct(m.stroke_iou)+(m.exact?' · 完整恢复':' · 存在恢复错误');}
$('sample').onchange=refreshCases;['case','view','reference'].forEach(id=>$(id).onchange=render);
$('slider').oninput=divider;$('attack').onchange=recovery;$('toggle').onclick=()=>{
$('slider').value=+$('slider').value===100?0:100;divider();};
window.onresize=()=>{if($('view').value==='overview')$('candidate').style.width=$('stage').clientWidth+'px';};
refreshCases();
</script></html>"""
    with (root / "index.html").open("x", encoding="utf-8") as stream:
        stream.write(page.replace("__DATA__", data))


def summary_sheet(root: Path, sample: dict, selected: str) -> None:
    """Export 1:1 crop comparisons and real recovered strokes as a local PNG."""
    directory = root / sample["id"]
    case = next(row for row in sample["cases"] if row["name"] == selected)
    with Image.open(directory / "baseline-smooth.png") as crop:
        size = crop.width
    padding, header, label = 20, 100, 34
    width = size * 3 + padding * 4
    height = header + 3 * (size + label + padding) + 420
    sheet = Image.new("RGB", (width, height), "#10151d")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    draw.text((padding, 18), f"{sample['id']} / {selected} / 100% crops", font=font, fill="white")
    metrics = case["versus_baseline"]
    draw.text(
        (padding, 52),
        f"PSNR vs baseline {metrics['psnr_rgb_db']:.2f} dB | "
        f"Y-SSIM {metrics['ssim_y']:.6f} | JPEG Q75 BER "
        f"{case['attacks']['jpeg_q75']['ber']:.3%}",
        font=font,
        fill="#bbc9da",
    )
    for row, kind in enumerate(("smooth", "detail", "shadow")):
        top = header + row * (size + label + padding)
        columns = [
            (f"baseline-{kind}.png", f"{kind}: JPEG baseline"),
            (f"{selected}-{kind}.png", f"{kind}: signature embedded"),
            (f"{selected}-{kind}-diff.png", "absolute difference x16"),
        ]
        for col, (filename, caption) in enumerate(columns):
            left = padding + col * (size + padding)
            draw.text((left, top), caption, font=font, fill="white")
            with Image.open(directory / filename) as image:
                sheet.paste(image.convert("RGB"), (left, top + label))
    top = header + 3 * (size + label + padding)
    for col, (filename, caption) in enumerate(
        [
            (root / "signature-embedded.png", "Embedded strokes"),
            (directory / f"{selected}-signature.png", "Recovered from saved Q95 JPEG"),
            (directory / f"{selected}-jpeg_q75-signature.png", "Recovered after Q75 / 4:2:0"),
        ]
    ):
        left = padding + col * (size + padding)
        draw.text((left, top), caption, font=font, fill="white")
        with Image.open(filename) as image:
            sheet.paste(image.convert("RGB"), (left, top + label))
    png(directory / "review-sheet.png", sheet)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, nargs="+", required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--with-visible-watermark", action="store_true")
    args = parser.parse_args()
    inputs = {p.resolve(): digest(p) for p in [*args.sources, args.signature]}
    resources = replace(
        local_project_resources(Path(__file__).resolve().parents[1]), signature=args.signature
    )
    if args.with_visible_watermark:
        inputs.update(
            {
                p.resolve(): digest(p)
                for p in (resources.latin_font, resources.chinese_font, resources.signature)
            }
        )
    with Image.open(args.signature) as signature:
        bits = signature_bits(signature)
    # Validate capacity before creating any output directory.
    for source in args.sources:
        prepared = prepare_jpeg(source)
        for algorithm, levels in LEVELS.items():
            Spec(algorithm, prepared.pixels.size, bits.shape[::-1], min(levels.values())).validate()
    root = args.output_dir.resolve()
    if root in {p.parent for p in inputs}:
        parser.error("Choose a new output directory separate from source assets")
    root.mkdir(parents=True, exist_ok=False)
    save_bitmap(root / "signature-embedded.png", bits)
    key = secrets.token_hex(32)
    start = time.perf_counter()
    samples = [
        evaluate_source(source, root, i + 1, bits, key) for i, source in enumerate(args.sources)
    ]
    selected, reason = select_case(samples)
    if args.with_visible_watermark:
        for source, sample in zip(args.sources, samples, strict=True):
            sample["combination"] = combination(
                source, root, sample, selected, bits, key, resources
            )
    hashes_after = {str(p): digest(p) for p in inputs}
    intact = all(hashes_after[str(p)] == value for p, value in inputs.items())
    report = {
        "version": VERSION,
        "date": "2026-10-13",
        "samples": samples,
        "selected": selected,
        "selection_reason": reason,
        "signature_size": bits.shape[::-1],
        "stroke_fraction": float(bits.mean()),
        "encoding": {"quality": 95, "subsampling": 0},
        "metrics": "RGB PSNR; Y SSIM, 7x7 uniform, sample covariance, data_range=255, valid windows",
        "input_hashes_before": {str(p): value for p, value in inputs.items()},
        "input_hashes_after": hashes_after,
        "inputs_unchanged": intact,
        "total_seconds": time.perf_counter() - start,
        "numpy": np.__version__,
        "pillow": Image.__version__,
    }
    write_json(root / "report.json", report)
    gallery(root, report)
    for sample in samples:
        summary_sheet(root, sample, selected)
    if not intact:
        raise OSError("Input assets changed during the experiment")
    print(f"Selected {selected}: {reason}", flush=True)
    print(root / "index.html", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
