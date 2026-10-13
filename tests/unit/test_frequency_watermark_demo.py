"""Use only generated pixels/strokes to check experimental watermark claims."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

# Experiments are outside src and therefore absent from public app wheels.
_path = Path(__file__).resolve().parents[2] / "scripts" / "frequency_watermark_core.py"
_module_spec = importlib.util.spec_from_file_location("frequency_watermark_core", _path)
assert _module_spec is not None and _module_spec.loader is not None
core = importlib.util.module_from_spec(_module_spec)
sys.modules[_module_spec.name] = core
_module_spec.loader.exec_module(core)

KEY = "synthetic-public-test-key-only"


def pixels() -> np.ndarray:
    rng = np.random.default_rng(123)
    return rng.integers(70, 180, (384, 512, 3), dtype=np.uint8)


def strokes() -> np.ndarray:
    image = Image.new("RGBA", (100, 60))
    draw = ImageDraw.Draw(image)
    draw.line([(5, 50), (30, 4), (55, 50), (70, 12), (95, 40)], fill="white", width=9)
    return core.signature_bits(image, 20)


@pytest.mark.parametrize("algorithm", ["dct", "fft"])
def test_signature_survives_saved_jpeg_with_blind_extraction(algorithm: str) -> None:
    rgb, bits = pixels(), strokes()
    original = rgb.copy()
    spec = core.Spec(algorithm, (512, 384), bits.shape[::-1], 24, 3)
    marked, stats = core.embed(rgb, bits, spec, KEY)
    assert np.array_equal(rgb, original)
    assert stats["slot_count"] == bits.size * 3
    stream = BytesIO()
    Image.fromarray(marked).save(stream, format="JPEG", quality=95, subsampling=0)
    stream.seek(0)
    with Image.open(stream) as jpeg:
        reopened = np.asarray(jpeg.convert("RGB"))
    # No source image or expected signature is given to extract().
    recovered = core.extract(reopened, core.Spec.from_dict(spec.to_dict()), KEY)
    metrics = core.recovery_metrics(bits, recovered)
    assert metrics["ber"] < 0.02
    assert metrics["stroke_iou"] > 0.95
    assert core.psnr(rgb, reopened) > 30


@pytest.mark.parametrize("algorithm", ["dct", "fft"])
def test_wrong_key_and_unmarked_image_do_not_match_strokes(algorithm: str) -> None:
    rgb, bits = pixels(), strokes()
    spec = core.Spec(algorithm, (512, 384), bits.shape[::-1], 24, 3)
    marked, _ = core.embed(rgb, bits, spec, KEY)
    for candidate, key in ((rgb, KEY), (marked, "another-synthetic-test-key")):
        observed = core.extract(candidate, spec, key)
        metrics = core.recovery_metrics(bits, observed)
        assert 0.35 < metrics["ber"] < 0.65
        assert metrics["stroke_iou"] < 0.5


@pytest.mark.parametrize("algorithm", ["dct", "fft"])
def test_changed_size_needs_explicit_alignment(algorithm: str) -> None:
    spec = core.Spec(algorithm, (512, 384), (20, 12), 24, 3)
    with pytest.raises(ValueError, match="original size"):
        core.extract(pixels()[:320], spec, KEY)


@pytest.mark.parametrize("strength", [0, -1, float("nan"), float("inf")])
def test_invalid_strength_is_rejected(strength: float) -> None:
    with pytest.raises(ValueError, match="Strength"):
        core.Spec("dct", (512, 384), (20, 12), strength, 3).validate()


def test_insufficient_capacity_is_not_silently_shrunk() -> None:
    with pytest.raises(ValueError, match="capacity"):
        core.Spec("fft", (128, 128), (128, 77), 24).validate()


def test_uniform_window_ssim_matches_independent_brute_reference() -> None:
    # Numeric check independent of the integral-window implementation.
    a = pixels()[:12, :15]
    b = a.copy()
    b[4:8, 5:10, 0] += 8
    ya, yb = core.luminance(a).astype(float), core.luminance(b).astype(float)
    expected = []
    for row in range(6):
        for col in range(9):
            x = ya[row : row + 7, col : col + 7].ravel()
            y = yb[row : row + 7, col : col + 7].ravel()
            mx, my = x.mean(), y.mean()
            vx, vy = x.var(ddof=1), y.var(ddof=1)
            cov = np.sum((x - mx) * (y - my)) / 48
            c1, c2 = 2.55**2, 7.65**2
            expected.append(
                (2 * mx * my + c1) * (2 * cov + c2) / ((mx * mx + my * my + c1) * (vx + vy + c2))
            )
    assert core.ssim_y(a, b) == pytest.approx(np.mean(expected), abs=1e-10)
    assert core.ssim_y(a, a) == pytest.approx(1, abs=1e-10)
    assert core.psnr(a, a) is None


def test_ssim_stripe_boundaries_cover_every_valid_window() -> None:
    a, b = pixels()[:270, :20], pixels()[:270, :20].copy()
    b[125:140] = 90
    # Striping the public calculation into 128-row outputs must agree with
    # calculating all valid windows in one pass using the mean primitive.
    x, y = core.luminance(a).astype(float), core.luminance(b).astype(float)
    mx, my = core._mean7(x), core._mean7(y)
    vx = (core._mean7(x * x) - mx * mx) * 49 / 48
    vy = (core._mean7(y * y) - my * my) * 49 / 48
    cov = (core._mean7(x * y) - mx * my) * 49 / 48
    expected = (2 * mx * my + 2.55**2) * (2 * cov + 7.65**2)
    expected /= (mx * mx + my * my + 2.55**2) * (vx + vy + 7.65**2)
    assert core.ssim_y(a, b) == pytest.approx(expected.mean(), abs=1e-10)


def test_recovery_reports_stroke_errors_despite_sparse_background() -> None:
    expected = np.zeros((20, 20), dtype=bool)
    expected[5:15, 10] = True
    metrics = core.recovery_metrics(expected, np.zeros_like(expected))
    assert metrics["ber"] == 0.025
    assert metrics["stroke_recall"] == 0
    assert metrics["stroke_iou"] == 0
    assert not metrics["exact"]


def test_cli_refuses_existing_output_and_preserves_source(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    signature = tmp_path / "signature.png"
    Image.fromarray(pixels()).save(source, quality=95)
    core.bitmap_image(strokes()).save(signature)
    before_source, before_signature = source.read_bytes(), signature.read_bytes()
    output = tmp_path / "new-output"
    script = _path.with_name("frequency_watermark_demo.py")
    command = [
        sys.executable,
        str(script),
        "embed",
        "--source",
        str(source),
        "--signature",
        str(signature),
        "--output-dir",
        str(output),
        "--signature-width",
        "20",
        "--repeats",
        "3",
        "--strength",
        "24",
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    marked = (output / "watermarked.jpg").read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode != 0
    assert (output / "watermarked.jpg").read_bytes() == marked
    assert source.read_bytes() == before_source
    assert signature.read_bytes() == before_signature
