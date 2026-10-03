"""Stage frozen application artifacts without any local photo or font resources."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from aim_tool import __version__

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = ROOT / "dist/AutoImageMarkTool"
    forbidden = {".jpg", ".jpeg", ".nef", ".ttf", ".otf", ".ttc", ".png"}
    for path in bundle.rglob("*"):
        if path.is_file() and (
            path.suffix.lower() in forbidden
            or any(
                token in path.name.lower() for token in ("rawpy", "libraw", "trajan", "fangzheng")
            )
        ):
            raise ValueError(f"Unexpected private or deferred resource: {path.name}")
    destination = args.output.resolve()
    destination.relative_to(ROOT / "build")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(bundle / "_internal/licenses", destination / "licenses")
    if sys.platform == "win32":
        shutil.copy2(ROOT / "dist/AutoImageMarkTool.exe", destination / "AutoImageMarkTool.exe")
        shutil.make_archive(
            str(destination / "AutoImageMarkTool-windows-x64"),
            "zip",
            root_dir=bundle.parent,
            base_dir=bundle.name,
        )
    else:
        deb = ROOT / f"dist/auto-image-mark-tool_{__version__.replace('rc', '~rc')}_amd64.deb"
        shutil.copy2(deb, destination / deb.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
