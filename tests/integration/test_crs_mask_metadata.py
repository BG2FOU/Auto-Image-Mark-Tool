"""Synthetic editing lists reproduce ExifTool notices during real metadata copies."""

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.images import prepare_jpeg
from aim_tool.services.metadata import preserve_watermark_metadata


@pytest.mark.parametrize(
    "kind, mask_count, warning_field",
    (
        ("mask", 1, "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs"),
        ("mask", 2, "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs"),
        ("paint", 1, "crs:PaintBasedCorrectionsCorrectionMasksDabs"),
        ("ancestors", 1, "photoshop:DocumentAncestors"),
        ("history", 1, "xmpMM:History"),
        ("lightroom", 1, "lr:hierarchicalSubject"),
    ),
)
def test_large_editing_lists_preserve_watermark_metadata(
    tmp_path: Path, kind: str, mask_count: int, warning_field: str
) -> None:
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
    mask = (
        '<rdf:li rdf:parseType="Resource"><crs:GestureDabs><rdf:Seq>'
        f"{items}</rdf:Seq></crs:GestureDabs></rdf:li>"
    )
    body = (
        "<crs:MaskGroupBasedCorrections><rdf:Seq>"
        '<rdf:li rdf:parseType="Resource"><crs:CorrectionMasks><rdf:Seq>'
        f"{mask * mask_count}</rdf:Seq></crs:CorrectionMasks>"
        "</rdf:li></rdf:Seq></crs:MaskGroupBasedCorrections>"
    )
    if kind == "paint":
        body = body.replace("MaskGroupBasedCorrections", "PaintBasedCorrections").replace(
            "GestureDabs", "Dabs"
        )
    elif kind in {"ancestors", "lightroom"}:
        field = "photoshop:DocumentAncestors" if kind == "ancestors" else "lr:hierarchicalSubject"
        body = f"<{field}><rdf:Bag>{items}</rdf:Bag></{field}>"
    elif kind == "history":
        history = '<rdf:li stEvt:action="saved"/>' * 1001
        body = f"<xmpMM:History><rdf:Seq>{history}</rdf:Seq></xmpMM:History>"
    xml = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"'
        ' xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"'
        ' xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"'
        ' xmlns:lr="http://ns.adobe.com/lightroom/1.0/">'
        '<dc:rights><rdf:Alt><rdf:li xml:lang="x-default">Synthetic rights</rdf:li>'
        f"</rdf:Alt></dc:rights>{body}"
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
    with pytest.raises(ExifToolError, match=f"Extracted only 1000 {warning_field}") as error:
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
    if mask_count > 1:
        assert "extract all [x2] - " in str(error.value)
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
