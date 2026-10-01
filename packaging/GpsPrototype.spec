"""PyInstaller onedir prototype for the GPS-only command line application."""

from pathlib import Path
import sys

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
    [str(root / "scripts/batch_gps.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=tool_data + [(str(root / "LICENSE"), ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "PIL", "rawpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoImageMarkGps",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AutoImageMarkGps",
)
