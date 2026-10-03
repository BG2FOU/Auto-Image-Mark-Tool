# ruff: noqa: F821
"""One reviewed GPS/JPG-watermark spec; AIM_BUILD_MODE selects onedir or onefile."""

import os
import subprocess
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).resolve().parent
mode = os.environ.get("AIM_BUILD_MODE", "onedir")
if mode not in {"onedir", "onefile"}:
    raise SystemExit("Unsupported build mode")
if sys.platform == "win32":
    runtime = root / "tools/exiftool"
    if not (runtime / "exiftool.exe").is_file() or not (runtime / "exiftool_files").is_dir():
        raise SystemExit("Pinned Windows ExifTool runtime is missing")
    tool_data = [(str(runtime), "tools/exiftool")]
else:
    runtime = root / "tools/exiftool-13.59"
    if not (runtime / "exiftool").is_file() or not (runtime / "lib").is_dir():
        raise SystemExit("Pinned Linux ExifTool runtime is missing")
    tool_data = [
        (str(runtime / "exiftool"), "tools/exiftool-13.59"),
        (str(runtime / "lib"), "tools/exiftool-13.59/lib"),
        (str(runtime / "LICENSE"), "tools/exiftool-13.59"),
    ]
licenses = root / "build/jpg-licenses"
if not (licenses / "SOURCE_ARCHIVES.json").is_file():
    raise SystemExit("Collect checked licenses before freezing")
a = Analysis(
    [str(root / "packaging/entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=tool_data
    + collect_data_files("aim_tool.resources", includes=["default_templates.json"])
    + [
        (str(root / "LICENSE"), "."),
        (str(root / "THIRD_PARTY_NOTICES.md"), "."),
        (str(licenses), "licenses"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["rawpy", "tkinter", "matplotlib", "scipy", "IPython", "pytest"],
    noarchive=False,
)
if sys.platform == "linux":
    seen = set()
    for _, filename, _ in a.binaries:
        source = Path(filename)
        if not str(source).startswith(("/lib/", "/usr/lib/")):
            continue
        found = subprocess.run(
            ["dpkg-query", "-S", str(source)], capture_output=True, text=True, check=False
        )
        if found.returncode != 0:
            found = subprocess.run(
                ["dpkg-query", "-S", str(source.resolve())],
                capture_output=True,
                text=True,
                check=False,
            )
        if found.returncode == 0:
            package = found.stdout.split(": ", 1)[0].split(":", 1)[0]
            copyright_file = Path("/usr/share/doc") / package / "copyright"
            if package not in seen and copyright_file.is_file():
                a.datas.append(
                    (f"licenses/linux-system/{package}.txt", str(copyright_file), "DATA")
                )
                seen.add(package)
pyz = PYZ(a.pure)
options = dict(
    name="AutoImageMarkTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
if sys.platform == "win32":
    options["version"] = str(root / "build/jpg-version-info.txt")
if mode == "onefile":
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AutoImageMarkTool")
