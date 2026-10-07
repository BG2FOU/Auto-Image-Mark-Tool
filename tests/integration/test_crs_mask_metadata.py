"""Synthetic Adobe brush metadata reproduces the real 1000-item failure."""

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.images import prepare_jpeg
from aim_tool.services.metadata import preserve_watermark_metadata


def test_large_adobe_mask_list_preserves_watermark_metadata(tmp_path: Path) -> None:
    tool = ExifTool()
    source = tmp_path / "中文 & 蒙版.jpg"
    target = tmp_path / "中文 水印.jpg"
    Image.new("RGB", (40, 30), (30, 60, 90)).save(source)
    tool._run_for_path(
        source,
        "-overwrite_original",
        "-ExifIFD:DateTimeOriginal=2026:10:07 12:34:56",
        "-IFD0:Model=Synthetic camera",
    )
    tool.write_gps(source, 24.123456, 118.654321, -12.5)
    # Insert our own small XMP APP1 packet; no private photo or Adobe data is needed.
    items = "<rdf:li>0.1,0.2</rdf:li>" * 1001
    xml = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:rights><rdf:Alt><rdf:li xml:lang="x-default">Synthetic rights</rdf:li>'
        "</rdf:Alt></dc:rights><crs:MaskGroupBasedCorrections><rdf:Seq>"
        '<rdf:li rdf:parseType="Resource"><crs:CorrectionMasks><rdf:Seq>'
        '<rdf:li rdf:parseType="Resource"><crs:GestureDabs><rdf:Seq>'
        f"{items}</rdf:Seq></crs:GestureDabs></rdf:li></rdf:Seq></crs:CorrectionMasks>"
        "</rdf:li></rdf:Seq></crs:MaskGroupBasedCorrections>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    packet = b"http://ns.adobe.com/xap/1.0/\0" + xml.encode("utf-8")
    jpeg = source.read_bytes()
    source.write_bytes(
        jpeg[:2] + b"\xff\xe1" + (len(packet) + 2).to_bytes(2, "big") + packet + jpeg[2:]
    )
    original = sha256(source.read_bytes()).digest()
    prepared = prepare_jpeg(source)
    prepared.pixels.save(target, icc_profile=prepared.srgb_icc)
    pixels, icc = Image.open(target).tobytes(), prepared.srgb_icc
    # Prove this fixture emits the same warning that used to abort the transfer.
    with pytest.raises(ExifToolError, match="Extracted only 1000 crs:.*GestureDabs"):
        tool._run(
            "-charset",
            "filename=UTF8",
            "-@",
            "-",
            argfile_input=(
                f"-tagsFromFile\n{source}\n-ExifIFD:DateTimeOriginal\n"
                f"-overwrite_original\n{target}\n"
            ),
            reject_warnings=True,
        )
    preserve_watermark_metadata(tool, source, target)
    metadata = tool.metadata(target)
    assert metadata["ExifIFD:DateTimeOriginal"] == "2026:10:07 12:34:56"
    assert metadata["IFD0:Model"] == "Synthetic camera"
    assert metadata["XMP-dc:Rights"] == "Synthetic rights"
    assert tool.read_gps(source) == tool.read_gps(target)
    assert not any(key.startswith("XMP-crs:") for key in metadata)
    assert sha256(source.read_bytes()).digest() == original
    with Image.open(target) as output:
        assert output.tobytes() == pixels
        assert output.info["icc_profile"] == icc
