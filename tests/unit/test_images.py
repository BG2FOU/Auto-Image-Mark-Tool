"""Verify JPEG orientation and ICC assumptions before watermark export."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageCms

from aim_tool.services.images import prepare_jpeg


def test_orientation_is_applied_once_and_missing_profile_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "turned.jpg"
    image = Image.new("RGB", (40, 20), (20, 50, 100))
    exif = image.getexif()
    exif[274] = 6
    image.save(source, exif=exif)
    prepared = prepare_jpeg(source)
    assert prepared.pixels.size == (20, 40)
    assert prepared.warnings == ("No ICC profile; assumed sRGB for preview",)
    assert prepared.srgb_icc


def test_embedded_srgb_profile_is_converted_and_matches_output(tmp_path: Path) -> None:
    source = tmp_path / "profiled.jpg"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (24, 16), (10, 40, 80)).save(source, icc_profile=profile)
    prepared = prepare_jpeg(source)
    assert prepared.pixels.mode == "RGB"
    assert prepared.pixels.size == (24, 16)
    assert prepared.warnings == ()
    assert prepared.srgb_icc == profile


def test_untagged_cmyk_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (24, 16), (10, 20, 30, 40)).save(source)
    with pytest.raises(ValueError, match="ambiguous color mode"):
        prepare_jpeg(source)


@pytest.mark.parametrize(
    ("orientation", "top_left_color", "size"),
    [
        (1, (220, 20, 20), (80, 40)),
        (2, (20, 220, 20), (80, 40)),
        (3, (220, 220, 20), (80, 40)),
        (4, (20, 20, 220), (80, 40)),
        (5, (220, 20, 20), (40, 80)),
        (6, (20, 20, 220), (40, 80)),
        (7, (220, 220, 20), (40, 80)),
        (8, (20, 220, 20), (40, 80)),
    ],
)
def test_all_exif_orientations_transform_pixels_once(
    tmp_path: Path, orientation: int, top_left_color: tuple[int, int, int], size: tuple[int, int]
) -> None:
    image = Image.new("RGB", (80, 40))
    for color, box in (
        ((220, 20, 20), (0, 0, 40, 20)),
        ((20, 220, 20), (40, 0, 80, 20)),
        ((20, 20, 220), (0, 20, 40, 40)),
        ((220, 220, 20), (40, 20, 80, 40)),
    ):
        image.paste(color, box)
    exif = Image.Exif()
    exif[274] = orientation
    source = tmp_path / "orientation.jpg"
    image.save(source, quality=100, subsampling=0, exif=exif)
    prepared = prepare_jpeg(source)
    assert prepared.pixels.size == size
    assert all(
        abs(actual - expected) <= 3
        for actual, expected in zip(prepared.pixels.getpixel((5, 5)), top_left_color, strict=True)
    )
    assert prepared.pixels.getexif().get(274) in {None, 1}


@pytest.mark.parametrize(("mode", "progressive"), [("RGB", False), ("RGB", True), ("L", True)])
def test_baseline_progressive_and_grayscale_jpeg(
    tmp_path: Path, mode: str, progressive: bool
) -> None:
    source = tmp_path / "sample.jpg"
    Image.new(mode, (64, 32)).save(source, progressive=progressive)
    prepared = prepare_jpeg(source)
    assert prepared.pixels.size == (64, 32)
    assert prepared.pixels.mode == "RGB"
    assert prepared.srgb_icc


def test_invalid_icc_reports_error_instead_of_relabeling_pixels(tmp_path: Path) -> None:
    source = tmp_path / "broken-icc.jpg"
    Image.new("RGB", (64, 32)).save(source, icc_profile=b"invalid profile")
    with pytest.raises(ValueError, match="unreadable ICC"):
        prepare_jpeg(source)


def test_large_jpeg_is_rejected_before_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "limit.jpg"
    Image.new("RGB", (64, 32)).save(source)
    monkeypatch.setattr("aim_tool.services.images.MAX_JPEG_PIXELS", 100)
    with pytest.raises(ValueError, match="megapixel"):
        prepare_jpeg(source)


def test_profile_incompatible_with_pixel_mode_reports_error(tmp_path: Path) -> None:
    source = tmp_path / "mismatched-icc.jpg"
    rgb_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("CMYK", (24, 16)).save(source, icc_profile=rgb_profile)
    with pytest.raises(ValueError, match="unreadable ICC"):
        prepare_jpeg(source)
