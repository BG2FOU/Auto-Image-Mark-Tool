"""Preserve a reviewed metadata whitelist from the current JPEG artifact."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image

from aim_tool.services.exiftool import ExifTool, ExifToolError

# Deliberately exclude MakerNotes, thumbnails, dimensions, Orientation and ICC.
# GPS comes from the current artifact (the located copy in a combined workflow).
WATERMARK_TAGS = (
    "IFD0:Make",
    "IFD0:Model",
    "IFD0:Artist",
    "IFD0:Copyright",
    "ExifIFD:DateTimeOriginal",
    "ExifIFD:CreateDate",
    "ExifIFD:SubSecTime",
    "ExifIFD:SubSecTimeOriginal",
    "ExifIFD:SubSecTimeDigitized",
    "ExifIFD:OffsetTime",
    "ExifIFD:OffsetTimeOriginal",
    "ExifIFD:OffsetTimeDigitized",
    "ExifIFD:ExposureTime",
    "ExifIFD:FNumber",
    "ExifIFD:ExposureProgram",
    "ExifIFD:ISO",
    "ExifIFD:SensitivityType",
    "ExifIFD:StandardOutputSensitivity",
    "ExifIFD:RecommendedExposureIndex",
    "ExifIFD:ISOSpeed",
    "ExifIFD:ExposureCompensation",
    "ExifIFD:MeteringMode",
    "ExifIFD:LightSource",
    "ExifIFD:Flash",
    "ExifIFD:FocalLength",
    "ExifIFD:FocalLengthIn35mmFormat",
    "ExifIFD:LensInfo",
    "ExifIFD:LensMake",
    "ExifIFD:LensModel",
    "ExifIFD:LensSerialNumber",
    "ExifIFD:BodySerialNumber",
    "ExifIFD:WhiteBalance",
    "ExifIFD:ExposureMode",
    "GPS:all",
    "XMP-dc:Rights",
    "XMP-dc:Creator",
    "XMP-xmpRights:Marked",
    "XMP-xmpRights:WebStatement",
    "XMP-xmpRights:UsageTerms",
    "IPTC:CopyrightNotice",
    "IPTC:By-line",
    "IPTC:Credit",
)


def _equivalent(first: Any, second: Any) -> bool:
    if type(first) in {int, float} and type(second) in {int, float}:
        return math.isclose(first, second, rel_tol=1e-8, abs_tol=1e-6)
    return bool(first == second)


def preserve_watermark_metadata(tool: ExifTool, authority: Path, target: Path) -> None:
    """Copy/verify metadata on an encoded temporary JPEG before it is committed."""
    before = tool.metadata(authority, *(f"-{tag}" for tag in WATERMARK_TAGS))
    # Reject partial GPS instead of exporting a successful-looking damaged record.
    source_gps = tool.read_gps(authority)
    with Image.open(target) as encoded:
        if encoded.format != "JPEG":
            raise ValueError("Watermark metadata output must be JPEG")
        size = encoded.size
        icc = encoded.info.get("icc_profile")
        if not icc:
            raise ValueError("Encoded watermark output has no color profile")
    overrides = {
        "IFD0:Orientation": 1,
        "ExifIFD:ExifImageWidth": size[0],
        "ExifIFD:ExifImageHeight": size[1],
        "ExifIFD:ColorSpace": 1,
    }
    tags = WATERMARK_TAGS if any(tag != "SourceFile" for tag in before) else ()
    tool.copy_tags(authority, target, tags, overrides)
    after = tool.metadata(
        target, *(f"-{tag}" for tag in WATERMARK_TAGS), *(f"-{tag}" for tag in overrides)
    )
    for tag, value in before.items():
        if tag == "SourceFile":
            continue
        if tag.startswith("ExifTool:") or tag not in after or not _equivalent(value, after[tag]):
            raise ExifToolError(f"Watermark metadata readback differs: {tag}")
    if any(after.get(tag) != value for tag, value in overrides.items()):
        raise ExifToolError("Watermark orientation, dimensions or color space readback failed")
    output_gps = tool.read_gps(target)
    if source_gps is None:
        if output_gps is not None:
            raise ExifToolError("Watermark output acquired unexpected GPS")
    elif output_gps is None or not (
        abs(source_gps.latitude - output_gps.latitude) <= 1e-6
        and abs(source_gps.longitude - output_gps.longitude) <= 1e-6
    ):
        raise ExifToolError("Watermark output GPS differs from current artifact")
    stale = tool.metadata(target, "-IFD1:all", "-PreviewImage", "-JpgFromRaw")
    if any(tag != "SourceFile" for tag in stale):
        raise ExifToolError("Watermark output contains a stale preview or thumbnail")
    with Image.open(target) as verified:
        if verified.size != size or verified.info.get("icc_profile") != icc:
            raise ExifToolError("Metadata transfer changed pixels dimensions or ICC")
