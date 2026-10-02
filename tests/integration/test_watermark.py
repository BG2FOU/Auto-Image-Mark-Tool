"""Check the configurable watermark layer with local, untracked project assets."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from aim_tool.services.watermark import WatermarkConfig, WatermarkResources, render_watermark_layer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def resources(pytestconfig: pytest.Config) -> WatermarkResources:
    data = ROOT / "data"
    paths = (
        data / "TrajanPro-Bold.otf",
        data / "FangZhengShengShiKaiShuJianTi-Da.ttf",
        data / "NAME.png",
    )
    missing = [path for path in paths if not path.is_file()]
    if missing:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(f"Required private watermark assets are missing: {missing}")
        pytest.skip(f"Private watermark assets are missing: {missing}")
    return WatermarkResources(*paths)


@pytest.mark.parametrize(
    ("category", "content"),
    [
        ("aviation", "B-1356"),
        ("railway", "CR400BF-C-5162"),
        ("landscape", "哈齐客专松花江特大桥日落"),
    ],
)
def test_three_templates_visible_margin_and_single_opacity(
    resources: WatermarkResources, category: str, content: str
) -> None:
    config = WatermarkConfig(category, content, date(2026, 10, 1))  # type: ignore[arg-type]
    overlay = render_watermark_layer((1203, 803), config, resources)
    alpha = overlay.getchannel("A")
    bounds = alpha.getbbox()
    assert bounds is not None
    assert 1203 - bounds[2] == 5
    assert 803 - bounds[3] == 5
    assert 0 < alpha.getextrema()[1] <= 128


def test_custom_size_anchor_and_offsets_recompute_layout(resources: WatermarkResources) -> None:
    base = WatermarkConfig("aviation", "N766CK", date(2026, 10, 1))
    standard = render_watermark_layer((1203, 803), base, resources)
    changed = replace(
        base,
        font_size_pt=24,
        signature_width=120,
        anchor="top_left",
        offset_x=10,
        offset_y=20,
        color=(255, 210, 180),
        latin_opacity=0.3,
        signature_opacity=0.4,
    )
    overlay = render_watermark_layer((1203, 803), changed, resources)
    standard_bounds = standard.getchannel("A").getbbox()
    changed_bounds = overlay.getchannel("A").getbbox()
    assert standard_bounds is not None and changed_bounds is not None
    assert changed_bounds[0] == 7
    assert changed_bounds[1] == 9
    assert changed_bounds[2] - changed_bounds[0] < standard_bounds[2] - standard_bounds[0]
    assert overlay.getchannel("A").getextrema()[1] <= 102


def test_invalid_content_and_missing_font_fail_before_render(resources: WatermarkResources) -> None:
    base = WatermarkConfig("railway", "CR400BF-C-5162", date(2026, 10, 1))
    with pytest.raises(ValueError, match="content"):
        render_watermark_layer((1203, 803), replace(base, content="cr400bf"), resources)
    with pytest.raises(ValueError, match="unavailable"):
        render_watermark_layer(
            (1203, 803), base, replace(resources, latin_font=Path("/missing/latin.otf"))
        )


def test_single_jpeg_watermark_preserves_dimensions_and_source(
    tmp_path: Path, resources: WatermarkResources
) -> None:
    from hashlib import sha256

    from PIL import Image

    from aim_tool.services.images import watermark_jpeg_pixels

    source = tmp_path / "sample.jpg"
    Image.new("RGB", (1203, 803), (20, 40, 60)).save(source)
    original_hash = sha256(source.read_bytes()).digest()
    config = WatermarkConfig("aviation", "B-1356", date(2026, 10, 1))
    result = watermark_jpeg_pixels(source, config, resources)
    assert result.pixels.size == (1203, 803)
    assert result.srgb_icc
    assert result.pixels.getpixel((0, 0)) != result.pixels.getpixel((1190, 790))
    assert sha256(source.read_bytes()).digest() == original_hash


def test_preview_export_preserves_orientation_profile_and_source(
    tmp_path: Path, resources: WatermarkResources
) -> None:
    from hashlib import sha256

    from PIL import Image, ImageCms

    from aim_tool.services.images import export_watermark_preview

    input_root = tmp_path / "input"
    input_root.mkdir()
    source = input_root / "source.jpg"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    image = Image.new("RGB", (1203, 803), (20, 40, 60))
    exif = image.getexif()
    exif[274] = 6
    image.save(source, exif=exif, icc_profile=profile, dpi=(300, 300))
    original_hash = sha256(source.read_bytes()).digest()
    target = tmp_path / "output" / "source_marked.jpg"
    config = WatermarkConfig("aviation", "B-1356", date(2026, 10, 1))
    assert export_watermark_preview(source, target, config, resources) == ()
    with Image.open(target) as output:
        assert output.size == (803, 1203)
        assert output.getexif().get(274) == 1
        assert output.info.get("icc_profile") == profile
        assert output.info.get("dpi") == (300, 300)
    assert sha256(source.read_bytes()).digest() == original_hash
    with pytest.raises(FileExistsError):
        export_watermark_preview(source, target, config, resources)
    with pytest.raises(ValueError, match="directory"):
        export_watermark_preview(source, input_root / "other.jpg", config, resources)


def test_full_resolution_signature_and_visible_margin(resources: WatermarkResources) -> None:
    from aim_tool.services.watermark import _scaled_signature

    signature = _scaled_signature(resources.signature, 300, 0.5)
    assert signature.size == (300, 181)
    assert signature.getchannel("A").getextrema()[1] == 128
    overlay = render_watermark_layer(
        (6016, 4016), WatermarkConfig("aviation", "LX-VCF", date(2026, 9, 13)), resources
    )
    bounds = overlay.getchannel("A").getbbox()
    assert bounds is not None
    assert 6016 - bounds[2] == 25
    assert 4016 - bounds[3] == 25
    assert overlay.getchannel("A").getextrema()[1] == 128


def test_explicit_local_font_copy_renders_without_fallback(
    tmp_path: Path, resources: WatermarkResources
) -> None:
    from shutil import copyfile

    selected = tmp_path / "selected.otf"
    copyfile(resources.latin_font, selected)
    config = WatermarkConfig("railway", "CR400BF-C-5162", date(2026, 9, 13))
    original = render_watermark_layer((1203, 803), config, resources)
    overridden = render_watermark_layer(
        (1203, 803), config, replace(resources, latin_font=selected)
    )
    assert original.tobytes() == overridden.tobytes()
    with pytest.raises(ValueError, match="missing glyphs"):
        render_watermark_layer(
            (1203, 803), config, replace(resources, latin_font=resources.chinese_font)
        )


def test_project_default_templates_and_signature_vertical_adjustment(
    resources: WatermarkResources,
) -> None:
    from aim_tool.services.templates import project_default_config

    categories = (
        ("aviation", "B-1356"),
        ("railway", "CR400BF-C-5162"),
        ("landscape", "哈齐客专松花江特大桥日落"),
    )
    for category, content in categories:
        config = project_default_config(category, content, date(2026, 10, 1))  # type: ignore[arg-type]
        assert config.font_size_pt == 36
        assert config.signature_width == 300
        assert config.margin_x == config.margin_y == 25
        assert config.color == (255, 255, 255)
        assert config.latin_opacity == config.chinese_opacity == config.signature_opacity == 0.5
        assert config.base_ppi == 300
        default_layer = render_watermark_layer((1203, 803), config, resources)
        adjusted_layer = render_watermark_layer(
            (1203, 803), replace(config, signature_offset_y=-20), resources
        )
        assert default_layer.tobytes() != adjusted_layer.tobytes()
        for layer in (default_layer, adjusted_layer):
            bounds = layer.getchannel("A").getbbox()
            assert bounds is not None
            assert 1203 - bounds[2] == 5
            assert 803 - bounds[3] == 5


def test_custom_signature_is_resized_without_changing_source(
    tmp_path: Path, resources: WatermarkResources
) -> None:
    from hashlib import sha256

    from PIL import Image

    from aim_tool.services.watermark import _scaled_signature

    signature = tmp_path / "custom.png"
    Image.new("RGBA", (20, 10), (180, 80, 40, 200)).save(signature)
    original_hash = sha256(signature.read_bytes()).digest()
    scaled = _scaled_signature(signature, 100, 0.5)
    assert scaled.size == (100, 50)
    assert scaled.getchannel("A").getextrema()[1] == 100
    assert all(
        abs(actual - expected) <= 1
        for actual, expected in zip(scaled.getpixel((50, 25))[:3], (180, 80, 40))
    )
    assert sha256(signature.read_bytes()).digest() == original_hash
    config = WatermarkConfig("aviation", "B-1356", date(2026, 10, 1))
    original = render_watermark_layer((1203, 803), config, resources)
    replaced = render_watermark_layer((1203, 803), config, replace(resources, signature=signature))
    assert original.tobytes() != replaced.tobytes()
