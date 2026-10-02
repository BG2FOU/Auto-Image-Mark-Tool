"""Build and smoke the Linux amd64 GPS GUI preview DEB."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from aim_tool import __version__

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "auto-image-mark-gps-gui"
VERSION = __version__.replace("rc", "~rc")


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
        "build/gps-gui-deb-pyinstaller",
        "packaging/GpsGui.spec",
    )
    binary = ROOT / "dist/AutoImageMarkGpsGui/AutoImageMarkGpsGui"
    run(
        sys.executable,
        "scripts/smoke_gps_gui.py",
        "--exe",
        str(binary),
        "--version",
        __version__,
    )

    stage = ROOT / "build/gps-gui-deb-stage"
    if stage.exists():
        shutil.rmtree(stage)
    app = stage / "opt/auto-image-mark-gps-gui"
    shutil.copytree(binary.parent, app, symlinks=True)
    wrapper = stage / "usr/bin/auto-image-mark-gps-gui"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        '#!/bin/sh\nexec /opt/auto-image-mark-gps-gui/AutoImageMarkGpsGui "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    desktop = stage / "usr/share/applications/auto-image-mark-gps-gui.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=Auto Image Mark GPS\n"
        "Exec=auto-image-mark-gps-gui\nTerminal=false\nCategories=Graphics;Photography;\n",
        encoding="utf-8",
    )
    docs = stage / f"usr/share/doc/{PACKAGE}"
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", docs / "copyright")
    shutil.copy2(ROOT / "packaging/GPS_GUI_THIRD_PARTY_NOTICES.md", docs / "THIRD_PARTY_NOTICES.md")
    shutil.copy2(runtime / "LICENSE", docs / "ExifTool-LICENSE")
    control = stage / "DEBIAN/control"
    control.parent.mkdir()
    control.write_text(
        f"Package: {PACKAGE}\nVersion: {VERSION}\nSection: graphics\nPriority: optional\n"
        "Architecture: amd64\n"
        "Depends: perl-base, libgl1, libegl1, libfontconfig1, libfreetype6, "
        "libglib2.0-0t64 | libglib2.0-0, libdbus-1-3, libx11-6, libx11-xcb1, "
        "libxkbcommon0, libxkbcommon-x11-0, libxcb1, libxcb-cursor0, "
        "libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, "
        "libxcb-render-util0, libxcb-shape0, libxcb-xfixes0, libxcb-xkb1\n"
        "Maintainer: BG2FOU <johnherbertwang@outlook.com>\n"
        "Description: GPS batch GUI preview for Auto Image Mark Tool\n"
        " Writes WGS84 GPS coordinates to copies of JPEG photos.\n",
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
