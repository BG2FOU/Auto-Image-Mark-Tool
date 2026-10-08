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
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageCms

from aim_tool.domain import BatchJob, ItemStatus, PhotoItem
from aim_tool.self_test_jpg import _resources
from aim_tool.services.exiftool import ExifTool
from aim_tool.workflow.engine import build_plan, run_plan
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


def measure(flow: str, count: int, size: tuple[int, int]) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="aim-benchmark-") as name:
        root = Path(name)
        resources = _resources(root)
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

        class MeasuredTool(ExifTool):
            def _run(self, *args: str, **kwargs: object) -> str:
                nonlocal calls, exif_seconds
                start = perf_counter()
                try:
                    return super()._run(*args, **kwargs)  # type: ignore[arg-type]
                finally:
                    calls += 1
                    exif_seconds += perf_counter() - start

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
        job = BatchJob(tuple(photos), preset(flow), root / "output")
        calls = 0
        exif_seconds = 0.0
        try:
            start = perf_counter()
            plan = build_plan(job, registry)
            preflight = perf_counter() - start
            preflight_calls, preflight_exif = calls, exif_seconds
            calls = 0
            exif_seconds = 0.0
            start = perf_counter()
            results = run_plan(plan)
            execution = perf_counter() - start
            if any(result.status != ItemStatus.SUCCESS for result in results):
                raise RuntimeError(str([result.error for result in results]))
            return {
                "flow": flow,
                "count": count,
                "size": size,
                "input_bytes_each": source.stat().st_size,
                "preflight_seconds": preflight,
                "execution_seconds": execution,
                "preflight_exiftool_calls": preflight_calls,
                "execution_exiftool_calls": calls,
                "preflight_exiftool_seconds": preflight_exif,
                "execution_exiftool_seconds": exif_seconds,
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
    parser.add_argument("--width", type=int, default=5038)
    parser.add_argument("--height", type=int, default=3363)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--child", choices=("location_only", "watermark_only", "location_and_watermark")
    )
    args = parser.parse_args()
    if min(args.count, args.rounds, args.width, args.height) < 1:
        parser.error("Counts and dimensions must be positive")
    if args.child:
        print(json.dumps(measure(args.child, args.count, (args.width, args.height))))
        return 0
    if args.report is None:
        parser.error("--report is required")
    records = []
    for flow in ("location_only", "watermark_only", "location_and_watermark"):
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
    for flow in ("location_only", "watermark_only", "location_and_watermark"):
        selected = [record for record in records if record["flow"] == flow]
        summary[flow] = {
            key: statistics.median(record[key] for record in selected)
            for key in ("preflight_seconds", "execution_seconds", "main_peak_rss_mib")
            if all(record[key] is not None for record in selected)
        }
    report = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": sys.platform,
        "scope": "Generated tiled-noise JPEGs and synthetic assets; filesystem cache not flushed; "
        "fresh Python process per round; RSS excludes ExifTool children and is not per phase.",
        "records": records,
        "medians": summary,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
