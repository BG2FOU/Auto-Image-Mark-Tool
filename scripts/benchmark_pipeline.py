"""Measure isolated preflight/execution with generated assets; write only a local report."""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import tempfile
from dataclasses import replace
from math import ceil
from pathlib import Path
from threading import Lock
from time import perf_counter

from benchmark_metrics import Metrics
from PIL import Image, ImageCms, ImageDraw

from aim_tool.domain import BatchJob, ItemResult, ItemStatus, PhotoItem
from aim_tool.self_test_jpg import _resources
from aim_tool.services.exiftool import ExifTool
from aim_tool.workflow.engine import ExecutionPlan, PlannedItem, build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep, RawDevelopStep, WatermarkStep

ROOT = Path(__file__).resolve().parents[1]


def peak_rss_mib() -> float | None:
    """Report main-process high-water RSS; ExifTool children are excluded."""
    if sys.platform == "linux":
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    return None


def gui_measure(root, photos, resources, flow, params, metrics, entry):
    from PySide6.QtWidgets import QApplication

    from aim_tool.self_test_jpg import _wait
    from aim_tool.services.storage import ConfigStore, WatermarkSettings, WatermarkSettingsStore
    from aim_tool.ui.main_window import MainWindow

    application = QApplication.instance() or QApplication([])
    store = WatermarkSettingsStore(root / "settings.json")
    store.save(WatermarkSettings(resources, params))
    window = MainWindow(
        settings_store=store,
        location_store=ConfigStore(root / "locations.json"),
        workflow_store=ConfigStore(root / "workflows.json"),
    )
    window.show()
    window.add_photos(tuple(photo.source for photo in photos))
    window.workflow.presets.setCurrentIndex(
        {"location_only": 0, "watermark_only": 1, "location_and_watermark": 2}[flow]
    )
    window.bulk_subject.setText("B-1356")
    window.apply_fields_button.click()
    window.apply_coordinates(24.2, 118.4)
    window.output_edit.setText(str(root / "output"))
    _wait(lambda: not window.has_active_workers, 120)
    checked = 0.0
    try:
        if entry == "gui-check-start":
            metrics.phase = "manual_check"
            start = perf_counter()
            window.check_button.click()
            _wait(lambda: not window._busy, 300)
            checked = perf_counter() - start
            if window.last_plan is None:
                raise RuntimeError(window.log.toPlainText())
        metrics.phase = "start_to_complete"
        start = perf_counter()
        window.start_button.click()
        _wait(lambda: not window._busy, 600)
        elapsed = perf_counter() - start
        return window.results, checked, elapsed
    finally:
        window.close()
        _wait(lambda: not window.has_active_workers, 120)
        application.processEvents()


def measure(
    flow: str,
    count: int,
    size: tuple[int, int],
    workers: int = 1,
    digital: str = "off",
    level: str = "medium",
    entry: str = "pipeline",
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="aim-benchmark-") as name:
        root = Path(name)
        resources = _resources(root)
        signature = Image.new("RGBA", (100, 60))
        ImageDraw.Draw(signature).line(
            [(5, 50), (30, 5), (55, 50), (80, 8), (95, 35)], fill="white", width=5
        )
        signature.save(resources.signature)
        inputs = root / "input"
        inputs.mkdir()
        tile = Image.frombytes("RGB", (256, 256), random.Random(20261009).randbytes(256**2 * 3))
        image = Image.new("RGB", size)
        for y in range(0, size[1], tile.height):
            for x in range(0, size[0], tile.width):
                image.paste(tile, (x, y))
        exif = Image.Exif()
        exif[34665] = {36867: "2026:10:09 12:00:00"}
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        source = inputs / "generated.jpg"
        image.save(source, quality=95, subsampling=0, exif=exif, icc_profile=profile)
        image.close()
        photos = []
        for index in range(count):
            path = inputs / f"generated-{index}.jpg"
            os.link(source, path)
            photos.append(
                PhotoItem(
                    path,
                    inputs,
                    coordinates=(24.2, 118.4),
                    edits={"category": "aviation", "subject": "B-1356"},
                )
            )
        calls = 0
        exif_seconds = 0.0
        metrics_lock = Lock()

        class MeasuredTool(ExifTool):
            def _run(self, *args: str, **kwargs: object) -> str:
                nonlocal calls, exif_seconds
                start = perf_counter()
                try:
                    return super()._run(*args, **kwargs)  # type: ignore[arg-type]
                finally:
                    elapsed = perf_counter() - start
                    with metrics_lock:
                        calls += 1
                        exif_seconds += elapsed

        # The adapter default is the compatibility mode; use the application's mode
        # once persistent sessions are supported by this checkout.
        options = {"persistent": True} if hasattr(ExifTool, "close") else {}
        tool = MeasuredTool(**options)
        registry = StepRegistry()
        for step in (
            LocationStep(tool, clear_auxiliary_gps=True),
            RawDevelopStep(),
            WatermarkStep(tool, resources),
            ExportStep(),
        ):
            registry.register(step)
        params = {
            "digital_enabled": digital != "off",
            "digital_algorithm": digital if digital != "off" else "dct",
            "digital_level": level,
            "digital_key": "ab" * 32,
        }
        workflow = preset(flow)
        workflow = replace(
            workflow,
            steps=tuple(
                replace(step, params={**step.params, **params})
                if step.component_id == "watermark"
                else step
                for step in workflow.steps
            ),
        )
        job = BatchJob(tuple(photos), workflow, root / "output")
        calls = 0
        exif_seconds = 0.0
        try:
            latencies = []
            with Metrics() as metrics:
                if entry != "pipeline":
                    results, preflight, execution = gui_measure(
                        root, photos, resources, flow, params, metrics, entry
                    )
                    preflight_calls = preflight_exif = None
                else:
                    metrics.phase = "preflight"
                    start = perf_counter()
                    plan = build_plan(job, registry)
                    preflight = perf_counter() - start
                    preflight_calls, preflight_exif = calls, exif_seconds
                    # Match GUI workers: preflight closes its session; execution reopens it.
                    tool.close()
                    calls = 0
                    exif_seconds = 0.0
                    metrics.phase = "execution"
                    start = perf_counter()

                    def execute_item(item: PlannedItem) -> tuple[ItemResult, ...]:
                        item_start = perf_counter()
                        batch = run_plan(ExecutionPlan((item,)))
                        with metrics_lock:
                            latencies.append(perf_counter() - item_start)
                        return batch

                    if workers == 1:
                        batches = [execute_item(item) for item in plan.items]
                    else:
                        # Exercise bounded production dispatch and collect task-local durations.
                        batches = [run_plan(plan, workers=workers)]
                    results = tuple(result for batch in batches for result in batch)
                    execution = perf_counter() - start
                    if workers == 2:
                        latencies = metrics.photo_seconds
            if any(result.status != ItemStatus.SUCCESS for result in results):
                raise RuntimeError(str([result.error for result in results]))
            return {
                "flow": flow,
                "count": count,
                "workers": workers,
                "digital": digital,
                "level": level,
                "entry": entry,
                "size": size,
                "input_bytes_each": source.stat().st_size,
                "preflight_seconds": preflight,
                "execution_seconds": execution,
                "total_seconds": preflight + execution,
                "photos_per_second": len(results) / execution,
                "photo_seconds": latencies,
                "photo_p50_seconds": statistics.median(latencies) if latencies else None,
                "photo_p95_seconds": sorted(latencies)[ceil(len(latencies) * 0.95) - 1]
                if latencies
                else None,
                "inclusive_stages": metrics.stages,
                "process_tree_sampled_peaks": metrics.memory,
                "memory_sampling_error": metrics.memory_error,
                "preflight_exiftool_calls": preflight_calls,
                "execution_exiftool_calls": calls if entry == "pipeline" else None,
                "preflight_exiftool_seconds": preflight_exif,
                "execution_exiftool_seconds": exif_seconds if entry == "pipeline" else None,
                "main_peak_rss_mib": peak_rss_mib(),
                "success_count": len(results),
            }
        finally:
            if hasattr(tool, "close"):
                tool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    parser.add_argument("--width", type=int, default=5038)
    parser.add_argument("--height", type=int, default=3363)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--digital", choices=("off", "dct", "fft"), default="off")
    parser.add_argument("--level", choices=("low", "medium", "high"), default="medium")
    parser.add_argument(
        "--entry", choices=("pipeline", "gui-start", "gui-check-start"), default="pipeline"
    )
    parser.add_argument(
        "--flow",
        choices=("all", "location_only", "watermark_only", "location_and_watermark"),
        default="all",
    )
    parser.add_argument(
        "--child", choices=("location_only", "watermark_only", "location_and_watermark")
    )
    args = parser.parse_args()
    if min(args.count, args.rounds, args.width, args.height) < 1:
        parser.error("Counts and dimensions must be positive")
    if args.entry != "pipeline" and args.workers != 1:
        parser.error("GUI measurements use the production execution policy")
    if args.child:
        print(
            json.dumps(
                measure(
                    args.child,
                    args.count,
                    (args.width, args.height),
                    args.workers,
                    args.digital,
                    args.level,
                    args.entry,
                )
            )
        )
        return 0
    if args.report is None:
        parser.error("--report is required")
    records = []
    flows = (
        ("location_only", "watermark_only", "location_and_watermark")
        if args.flow == "all"
        else (args.flow,)
    )
    for flow in flows:
        for iteration in range(args.rounds):
            output = subprocess.check_output(
                [
                    sys.executable,
                    __file__,
                    "--child",
                    flow,
                    "--count",
                    str(args.count),
                    "--width",
                    str(args.width),
                    "--height",
                    str(args.height),
                    "--workers",
                    str(args.workers),
                    "--digital",
                    args.digital,
                    "--level",
                    args.level,
                    "--entry",
                    args.entry,
                ],
                cwd=ROOT,
                text=True,
            )
            record = json.loads(output)
            record["iteration"] = iteration
            records.append(record)
            print(
                f"{flow} round {iteration + 1}: "
                f"preflight {record['preflight_seconds']:.3f}s; "
                f"execute {record['execution_seconds']:.3f}s",
                flush=True,
            )
    summary = {}
    for flow in flows:
        selected = [record for record in records if record["flow"] == flow]
        summary[flow] = {
            key: statistics.median(record[key] for record in selected)
            for key in (
                "preflight_seconds",
                "execution_seconds",
                "total_seconds",
                "main_peak_rss_mib",
            )
            if all(record[key] is not None for record in selected)
        }
    report = {
        "source_sha": os.environ.get("AIM_BENCHMARK_SOURCE_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": sys.version,
        "platform": sys.platform,
        "workers": args.workers,
        "scope": "Generated tiled-noise JPEG hardlinks and synthetic assets; filesystem cache not flushed; "
        "fresh Python process per round; main high-water RSS includes setup; sampled process-tree peaks "
        "sum simultaneous working sets (shared pages may be counted repeatedly), sampled every 25ms; "
        "stages are inclusive and overlap; GUI start includes automatic preflight; GUI setup/import excluded; "
        "ExifTool timings include session-lock wait; per-photo p95 is empirical with small sample limits.",
        "records": records,
        "medians": summary,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
