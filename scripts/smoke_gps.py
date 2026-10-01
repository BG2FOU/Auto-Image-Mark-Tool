"""Smoke a frozen GPS-only executable with two synthetic JPEGs."""

from __future__ import annotations

import argparse
import csv
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path

from PIL import Image

from aim_tool.services.exiftool import ExifTool


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    executable = args.exe.resolve()
    if not executable.is_file():
        parser.error(f"Executable is missing: {executable}")
    with tempfile.TemporaryDirectory(prefix="aim-gps-smoke-") as temp:
        root = Path(temp)
        input_root = root / "input"
        nested = input_root / "中文 目录"
        nested.mkdir(parents=True)
        first = nested / "甲.jpg"
        second = input_root / "b.JPEG"
        Image.new("RGB", (40, 30), (10, 20, 30)).save(first)
        Image.new("RGB", (32, 24), (50, 60, 70)).save(second)
        source_hashes = {path: sha256(path.read_bytes()).digest() for path in (first, second)}
        table = root / "rows.csv"
        with table.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(("file_name", "latitude", "longitude"))
            writer.writerow(("中文 目录/甲.jpg", "-24.123456789", "118.987654321"))
            writer.writerow(("b.JPEG", "0", "-180"))
        output_root = root / "output"
        command = [
            str(executable),
            "--csv",
            str(table),
            "--input-root",
            str(input_root),
            "--output-root",
            str(output_root),
        ]
        for execute in (False, True):
            completed = subprocess.run(
                [*command, *(["--execute"] if execute else [])],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=120,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr or completed.stdout)
            if not execute and output_root.exists():
                raise RuntimeError("Preflight wrote an output")
        tool = ExifTool()
        for source, expected in ((first, (-24.123456789, 118.987654321)), (second, (0, -180))):
            output = output_root / source.relative_to(input_root)
            gps = tool.read_gps(output)
            if gps is None or any(
                abs(actual - requested) > 1e-6
                for actual, requested in zip((gps.latitude, gps.longitude), expected, strict=True)
            ):
                raise RuntimeError(f"GPS readback failed: {output}")
            if sha256(source.read_bytes()).digest() != source_hashes[source]:
                raise RuntimeError(f"Source changed: {source}")
            with Image.open(source) as before, Image.open(output) as after:
                if before.tobytes() != after.tobytes():
                    raise RuntimeError(f"JPEG pixels changed: {output}")
        print("GPS frozen smoke passed: 2 JPEGs, GPS readback, original hashes and pixels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
