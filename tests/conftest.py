"""Shared pytest options for required external acceptance assets."""

from __future__ import annotations

from pathlib import Path

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image

from aim_tool.services.watermark import WatermarkResources


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-real-assets",
        action="store_true",
        help="fail rather than skip tests that require real photos",
    )
    parser.addoption(
        "--require-visual-assets",
        action="store_true",
        help="fail rather than skip tests that require approved visual baselines",
    )


@pytest.fixture
def synthetic_watermark_resources(tmp_path: Path) -> WatermarkResources:
    """Build our own block glyphs, without bundling or depending on licensed fonts."""
    font_path = tmp_path / "test.ttf"
    codes = (*range(32, 127), 169)
    cmap = {code: f"g{code}" for code in codes}
    glyphs = {}
    order = [".notdef", *cmap.values()]
    for name in order:
        pen = TTGlyphPen(None)
        if name != "g32":
            pen.moveTo((30, 0))
            pen.lineTo((450, 0))
            pen.lineTo((450, 700))
            pen.lineTo((30, 700))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (500, 0) for name in order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "AIM Synthetic", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.save(font_path)
    signature = tmp_path / "signature.png"
    Image.new("RGBA", (30, 18), (240, 240, 240, 255)).save(signature)
    return WatermarkResources(font_path, font_path, signature)
