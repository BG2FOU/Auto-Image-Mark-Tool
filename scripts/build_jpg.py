"""Build the full JPG edition with the pinned runtime, licenses, and frozen self-test."""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

from collect_licenses import collect

from aim_tool import __version__

ROOT = Path(__file__).resolve().parents[1]


def run(*command: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("onedir", "onefile"), default="onedir")
    args = parser.parse_args()
    if sys.version.split()[0] != "3.12.3":
        raise SystemExit("Build requires pinned Python 3.12.3")
    runtime = ROOT / (
        "tools/exiftool/exiftool.exe"
        if sys.platform == "win32"
        else "tools/exiftool-13.59/exiftool"
    )
    command = [str(runtime), "-ver"] if sys.platform == "win32" else ["perl", str(runtime), "-ver"]
    if subprocess.check_output(command, text=True).strip() != "13.59":
        raise SystemExit("Build requires pinned ExifTool 13.59")
    collect()
    if sys.platform == "win32":
        from packaging.version import Version

        version = Version(__version__)
        numeric = (*version.release[:3], version.pre[1] if version.pre else 0)
        info = f"""VSVersionInfo(
 ffi=FixedFileInfo(filevers={numeric!r}, prodvers={numeric!r}, mask=0x3f,
 flags={2 if version.is_prerelease else 0}, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
 kids=[StringFileInfo([StringTable('040904b0',[
 StringStruct('CompanyName','BG2FOU'),StringStruct('ProductName','Auto Image Mark Tool'),
 StringStruct('FileVersion',{__version__!r}),StringStruct('ProductVersion',{__version__!r}),
 StringStruct('LegalCopyright','CC BY-NC-SA 4.0 / BG2FOU')])]),
 VarFileInfo([VarStruct('Translation',[1033,1200])])])"""
        ast.parse(info)
        (ROOT / "build/jpg-version-info.txt").write_text(info, encoding="utf-8")
    environment = os.environ.copy()
    environment["AIM_BUILD_MODE"] = args.mode
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build/pyinstaller-cache")
    environment.pop("AIM_EXIFTOOL", None)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        "dist",
        "--workpath",
        f"build/jpg-{args.mode}",
        "packaging/AutoImageMarkTool.spec",
        env=environment,
    )
    filename = "AutoImageMarkTool.exe" if sys.platform == "win32" else "AutoImageMarkTool"
    bundle = ROOT / "dist" / ("AutoImageMarkTool" if args.mode == "onedir" else "")
    binary = bundle / filename
    run(sys.executable, "scripts/smoke_exe.py", "--exe", str(binary), "--version", __version__)
    print(binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
