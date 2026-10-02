"""Local-only asset identities and selected font faces."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from aim_tool.services.resources import (
    identify_signature,
    identify_watermark_assets,
    local_project_resources,
)
from aim_tool.services.watermark import WatermarkResources

ROOT = Path(__file__).resolve().parents[2]


def _resources(pytestconfig: pytest.Config) -> WatermarkResources:
    resources = local_project_resources(ROOT)
    files = (resources.latin_font, resources.chinese_font, resources.signature)
    if not all(path.is_file() for path in files):
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail("Required local-only watermark assets are missing")
        pytest.skip("Local-only watermark assets are missing")
    return resources


def test_default_asset_identities_match_local_manifest(pytestconfig: pytest.Config) -> None:
    resources = _resources(pytestconfig)
    manifest = json.loads((ROOT / "tests/fixtures/manifest.json").read_text(encoding="utf-8"))
    expected = {item["path"]: item["sha256"] for item in manifest["assets"]}
    identities = identify_watermark_assets(resources)
    assert identities.latin.sha256 == expected["data/TrajanPro-Bold.otf"]
    assert identities.latin.style == "Bold"
    assert identities.chinese.sha256 == expected["data/FangZhengShengShiKaiShuJianTi-Da.ttf"]
    assert identities.signature.sha256 == expected["data/NAME.png"]
    assert identities.signature.visible_bounds == (0, 0, 759, 459)
    with pytest.raises(ValueError, match="Invalid font face"):
        identify_watermark_assets(replace(resources, latin_face=1))


def test_empty_signature_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.png"
    Image.new("RGBA", (10, 10)).save(path)
    with pytest.raises(ValueError, match="no visible pixels"):
        identify_signature(path)
