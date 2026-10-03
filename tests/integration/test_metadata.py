"""Real ExifTool watermark metadata transfer without private assets."""

from __future__ import annotations

import shutil
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.images import prepare_jpeg
from aim_tool.services.metadata import preserve_watermark_metadata


@pytest.fixture
def tool(pytestconfig: pytest.Config) -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(str(error))
        pytest.skip(str(error))


def test_metadata_transfer_preserves_current_gps_and_camera_not_old_dimensions(
    tmp_path: Path, tool: ExifTool
) -> None:
    source = tmp_path / "中文 源片.jpg"
    image = Image.new("RGB", (60, 40), (10, 40, 80))
    exif = Image.Exif()
    exif[274] = 6
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    image.save(source, exif=exif, icc_profile=profile, dpi=(300, 300))
    thumbnail = tmp_path / "thumb.jpg"
    Image.new("RGB", (10, 8), "red").save(thumbnail)
    tool._run_for_path(
        source,
        "-overwrite_original",
        "-IFD0:Make=TEST",
        "-IFD0:Model=Camera",
        "-ExifIFD:DateTimeOriginal=2026:09:13 12:57:36",
        "-ExifIFD:FNumber=5.6",
        "-ExifIFD:LensModel=Test lens",
        "-IFD0:Copyright=Original copyright",
        "-XMP-dc:Rights=Original rights",
        "-IPTC:CopyrightNotice=Original IPTC",
        "-ExifIFD:ExifImageWidth=60",
        "-ExifIFD:ExifImageHeight=40",
        f"-ThumbnailImage<={thumbnail}",
    )
    tool.write_gps(source, -24.123456789, 118.987654321)
    before = sha256(source.read_bytes()).digest()
    prepared = prepare_jpeg(source)
    target = tmp_path / "水印 output.jpg"
    prepared.pixels.save(target, icc_profile=prepared.srgb_icc, dpi=prepared.dpi)
    pixels = Image.open(target).tobytes()
    preserve_watermark_metadata(tool, source, target)
    values = tool.metadata(target)
    assert values["IFD0:Orientation"] == 1
    assert values["ExifIFD:ExifImageWidth"] == 40
    assert values["ExifIFD:ExifImageHeight"] == 60
    assert values["ExifIFD:DateTimeOriginal"] == "2026:09:13 12:57:36"
    assert values["ExifIFD:LensModel"] == "Test lens"
    assert values["IFD0:Copyright"] == "Original copyright"
    assert values["XMP-dc:Rights"] == "Original rights"
    assert values["IPTC:CopyrightNotice"] == "Original IPTC"
    assert tool.read_gps(target) == tool.read_gps(source)
    assert "IFD1:ThumbnailImage" not in values
    with Image.open(target) as output:
        assert output.tobytes() == pixels
        assert output.info["icc_profile"] == prepared.srgb_icc
    assert sha256(source.read_bytes()).digest() == before


def test_untagged_source_does_not_gain_gps(tmp_path: Path, tool: ExifTool) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (30, 20)).save(source)
    prepared = prepare_jpeg(source)
    target = tmp_path / "target.jpg"
    prepared.pixels.save(target, icc_profile=prepared.srgb_icc)
    preserve_watermark_metadata(tool, source, target)
    assert tool.read_gps(target) is None


def test_partial_gps_is_rejected_before_transfer(tmp_path: Path, tool: ExifTool) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (30, 20)).save(source)
    tool._run_for_path(source, "-overwrite_original", "-GPS:GPSLatitude=1")
    prepared = prepare_jpeg(source)
    target = tmp_path / "target.jpg"
    prepared.pixels.save(target, icc_profile=prepared.srgb_icc)
    before = target.read_bytes()
    with pytest.raises(ExifToolError, match="incomplete"):
        preserve_watermark_metadata(tool, source, target)
    assert target.read_bytes() == before


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bundled Perl runtime")
def test_windows_runtime_in_unicode_directory(
    tmp_path: Path, tool: ExifTool, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "中文 程序" / "exiftool"
    shutil.copytree(tool.executable.parent, runtime)
    relocated = ExifTool(runtime / "exiftool.exe")
    source = tmp_path / "中文 照片.jpg"
    Image.new("RGB", (32, 24), (20, 40, 60)).save(source)
    with Image.open(source) as original:
        before = original.tobytes()
    monkeypatch.chdir(tmp_path)
    relocated.write_gps(Path(source.name), -24.2, 118.4)
    gps = relocated.read_gps(Path(source.name))
    assert gps is not None
    assert abs(gps.latitude + 24.2) < 1e-6
    assert abs(gps.longitude - 118.4) < 1e-6
    with Image.open(source) as output:
        assert output.tobytes() == before
