"""Build and smoke a Linux amd64 DEB of the GPS-only JPEG prototype."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "auto-image-mark-gps"
VERSION = "0.1.0~gps.1"


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    if sys.platform != "linux" or shutil.which("dpkg-deb") is None:
        raise SystemExit("Linux with dpkg-deb is required")
    runtime = ROOT / "tools/exiftool-13.59"
    if not (runtime / "exiftool").is_file() or not (runtime / "lib").is_dir():
        raise SystemExit("Pinned Linux ExifTool 13.59 runtime is missing")
    if (
        subprocess.check_output(["perl", str(runtime / "exiftool"), "-ver"], text=True).strip()
        != "13.59"
    ):
        raise SystemExit("Unexpected ExifTool version")

    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        "dist",
        "--workpath",
        "build/gps-deb-pyinstaller",
        "packaging/GpsPrototype.spec",
    )
    binary = ROOT / "dist/AutoImageMarkGps/AutoImageMarkGps"
    run(sys.executable, "scripts/smoke_gps.py", "--exe", str(binary))

    stage = ROOT / "build/gps-deb-stage"
    if stage.exists():
        shutil.rmtree(stage)
    app = stage / "opt/auto-image-mark-gps"
    shutil.copytree(binary.parent, app, symlinks=True)
    wrapper = stage / "usr/bin/auto-image-mark-gps"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        '#!/bin/sh\nexec /opt/auto-image-mark-gps/AutoImageMarkGps "$@"\n', encoding="utf-8"
    )
    wrapper.chmod(0o755)
    docs = stage / "usr/share/doc/auto-image-mark-gps"
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", docs / "copyright")
    shutil.copy2(ROOT / "packaging/THIRD_PARTY_NOTICES.md", docs / "THIRD_PARTY_NOTICES.md")
    shutil.copy2(runtime / "LICENSE", docs / "ExifTool-LICENSE")
    control = stage / "DEBIAN/control"
    control.parent.mkdir()
    control.write_text(
        f"Package: {PACKAGE}\nVersion: {VERSION}\nSection: graphics\nPriority: optional\n"
        "Architecture: amd64\nDepends: perl-base\nMaintainer: BG2FOU <johnherbertwang@outlook.com>\n"
        "Description: GPS-only JPEG batch prototype for Auto Image Mark Tool\n"
        " Writes WGS84 GPS coordinates to copies of JPEG photos from a CSV file.\n",
        encoding="utf-8",
    )
    output = ROOT / f"dist/{PACKAGE}_{VERSION}_amd64.deb"
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = subprocess.check_output(
        ["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT, text=True
    ).strip()
    subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output)],
        cwd=ROOT,
        env=env,
        check=True,
    )
    run("dpkg-deb", "--info", str(output))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
