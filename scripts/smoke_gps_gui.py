"""Smoke a frozen GPS GUI and its real ExifTool write path offline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    executable = args.exe.resolve()
    if not executable.is_file():
        parser.error(f"Executable is missing: {executable}")
    with tempfile.TemporaryDirectory(prefix="aim-gps-gui-smoke-") as temporary:
        report = Path(temporary) / "report.json"
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment.pop("AIM_EXIFTOOL", None)
        completed = subprocess.run(
            [str(executable), "--self-test", "--report", str(report)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                completed.stderr or completed.stdout or "Frozen GUI exited unsuccessfully"
            )
        if not report.is_file():
            raise RuntimeError("Frozen GUI did not write its self-test report")
        data = json.loads(report.read_text(encoding="utf-8"))
        expected = {
            "version": args.version,
            "gui_started": True,
            "exiftool": "13.59",
            "gps_roundtrip": True,
            "location_roundtrip": True,
            "source_unchanged": True,
            "pixels_unchanged": True,
        }
        if data != expected:
            raise RuntimeError(f"Unexpected frozen GUI self-test report: {data}")
    print(
        "Frozen GPS GUI smoke passed: window, location presets, ExifTool, GPS, source and JPEG pixels"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
