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
