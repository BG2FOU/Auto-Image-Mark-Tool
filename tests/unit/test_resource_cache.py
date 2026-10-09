"""Bounded resource reuse cannot conceal edits, missing glyphs, or canvas limits."""

import os
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from PIL import Image

from aim_tool.services import fonts, watermark
from aim_tool.services.watermark import WatermarkResources


def test_font_reuses_cmap_and_font_but_checks_every_new_text(
    synthetic_watermark_resources: WatermarkResources,
) -> None:
    path = synthetic_watermark_resources.latin_font
    first = fonts.load_checked_font(path, 0, "ABC", 20)
    assert fonts.load_checked_font(path, 0, "DEF", 20) is first
    assert fonts.load_checked_font(path, 0, "ABC", 21) is not first
    with pytest.raises(ValueError, match="missing glyphs"):
        fonts.load_checked_font(path, 0, "汉", 20)


def test_font_replacement_invalidates_coverage_with_restored_mtime(
    synthetic_watermark_resources: WatermarkResources,
) -> None:
    path = synthetic_watermark_resources.latin_font
    fonts.load_checked_font(path, 0, "A", 20)
    stat = path.stat()
    font = TTFont(path)
    for table in font["cmap"].tables:
        table.cmap.pop(ord("A"), None)
    font.save(path)
    font.close()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(ValueError, match="missing glyphs"):
        fonts.load_checked_font(path, 0, "A", 20)


def test_signature_reuse_is_bounded_and_returns_private_pixels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "signature.png"
    Image.new("RGBA", (10, 10), (255, 255, 255, 255)).save(path)
    monkeypatch.setattr(watermark, "_SIGNATURE_CACHE_LIMIT", 12000)
    with watermark._SIGNATURE_CACHE_LOCK:
        watermark._SIGNATURE_CACHE.clear()
    first = watermark._scaled_signature(path, 30, 0.5, max_size=(40, 40))
    first.putpixel((0, 0), (0, 0, 0, 0))
    assert watermark._scaled_signature(path, 30, 0.5).getpixel((0, 0))[3] == 128
    with pytest.raises(ValueError, match="does not fit"):
        watermark._scaled_signature(path, 30, 0.5, max_size=(20, 20))
    for width in range(30, 40):
        watermark._scaled_signature(path, width, 0.5)
    assert sum(im.width * im.height * 4 for im in watermark._SIGNATURE_CACHE.values()) <= 12000
    assert len(watermark._SIGNATURE_CACHE) <= 16
    stat = path.stat()
    Image.new("RGBA", (10, 10), (100, 100, 100, 255)).save(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert watermark._scaled_signature(path, 30, 0.5).getpixel((0, 0))[:3] == (100, 100, 100)
