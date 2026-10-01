"""S1 package and toolchain smoke tests."""

from __future__ import annotations

import json
import re
import struct
import sys
from importlib.metadata import version
from pathlib import Path

from aim_tool import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_package_version_has_one_source() -> None:
    assert version("auto-image-mark-tool") == __version__


def test_toolchain_manifest_is_fixed() -> None:
    manifest = json.loads((ROOT / "packaging/toolchain.json").read_text(encoding="utf-8"))
    assert sys.version.split()[0] == manifest["python"]["version"]
    assert struct.calcsize("P") * 8 == 64
    assert manifest["python"]["architecture"] == "x64"
    assert version("pip") == manifest["pip"]
    assert version("pip-tools") == manifest["pip_tools"]
    for package in ("python", "exiftool"):
        entry = manifest[package]
        assert entry["url"].startswith("https://")
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
        assert entry["license_url"].startswith("https://")
    for package in ("pip", "pip_tools"):
        entry = manifest["bootstrap_packages"][package]
        assert entry["version"] == manifest[package]
        assert entry["url"].startswith("https://")
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
    assert manifest["exiftool"]["archive_name"] in manifest["exiftool"]["url"]
