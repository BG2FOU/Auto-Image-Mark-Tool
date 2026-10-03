"""Run the complete frozen JPG self-test away from the repository and user settings."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from aim_tool import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--version", default=__version__)
    args = parser.parse_args()
    executable = args.exe.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="aim-jpg-frozen-") as name:
        temporary = Path(name)
        report = temporary / "report.json"
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment.pop("AIM_EXIFTOOL", None)
        environment.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [str(executable), "--self-test-jpg", "--report", str(report)],
            cwd=temporary,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        data = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        expected = {
            "version": args.version,
            "frozen": True,
            "ok": True,
            "exiftool": "13.59",
            "checks": [
                "gui",
                "settings",
                "locations",
                "preview",
                "gps_watermark",
                "orientation",
                "icc",
                "capture_date",
                "source_unchanged",
                "cleanup",
                "report",
                "xlsx",
            ],
        }
        if completed.returncode != 0 or data != expected:
            raise RuntimeError(f"Frozen JPG self-test failed: {data}\n{completed.stderr}")
    print(json.dumps(expected, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
