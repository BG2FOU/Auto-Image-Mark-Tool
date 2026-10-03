"""Validate the single source version, release tag, source commit and asset checksums."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_tag() -> str:
    tree = ast.parse((ROOT / "src/aim_tool/__init__.py").read_text(encoding="utf-8"))
    value = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    )
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:rc(\d+))?", value)
    if match is None:
        raise ValueError("Unsupported release version")
    return f"v{match[1]}" + (f"-rc.{match[2]}" if match[2] else "")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist/release")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    tag = release_tag()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if args.tag is not None:
        if args.tag != tag:
            raise ValueError("Tag and source version do not match")
        target = subprocess.check_output(
            ["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"], cwd=ROOT, text=True
        ).strip()
        if target != head:
            raise ValueError("Release tag does not identify this checkout")
    if not args.source_only:
        directory = args.dist.resolve()
        sums = (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        required = {
            f"AutoImageMarkTool-{tag}-windows-x64.exe",
            f"AutoImageMarkTool-{tag}-windows-x64.zip",
            f"auto-image-mark-tool_{tag.removeprefix('v')}_amd64.deb",
            "THIRD_PARTY_NOTICES.md",
            "LICENSES.zip",
            "BUILD_INFO.json",
        }
        names = set()
        for line in sums:
            expected, name = line.split("  ", 1)
            if (
                Path(name).name != name
                or name in names
                or not re.fullmatch(r"[a-f0-9]{64}", expected)
            ):
                raise ValueError("Invalid release checksum entry")
            names.add(name)
            if digest(directory / name) != expected:
                raise ValueError(f"Asset checksum mismatch: {name}")
        if names != required:
            raise ValueError(f"Unexpected release assets: {names ^ required}")
        info = json.loads((directory / "BUILD_INFO.json").read_text(encoding="utf-8"))
        if info["tag"] != tag or info["commit"] != head:
            raise ValueError("Build evidence does not match source")
        if (info["python"], info["pyinstaller"], info["exiftool"]) != ("3.12.3", "6.22.3", "13.59"):
            raise ValueError("Build toolchain does not match pinned versions")
        if (
            info["private_assets"] != "excluded"
            or info["nef"] != "gps_only_nikon_z5_14bit_lossless"
        ):
            raise ValueError("Release scope does not match the verified GPS/watermark edition")
    print(tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
