# ruff: noqa: F821

"""PyInstaller onefile build of the GPS graphical preview."""

import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parent
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
    ]

a = Analysis(
    [str(root / "packaging/gps_gui_entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=tool_data
    + [
        (str(root / "LICENSE"), "."),
        (str(root / "packaging/GPS_GUI_THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["rawpy", "openpyxl", "fontTools", "aim_tool.ui.main_window"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AutoImageMarkGpsGui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
