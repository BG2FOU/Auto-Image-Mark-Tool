"""Verify the tested NEF GPS profile and unchanged payloads without RAW decoding."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aim_tool.services.exiftool import ExifTool

# Only the locally tested camera/encoding is eligible for independent viewer approval.
PROFILE = {
    "IFD0:Make": "NIKON CORPORATION",
    "IFD0:Model": "NIKON Z 5",
    "Nikon:NEFCompression": 3,
    "SubIFD1:Compression": 34713,
    "SubIFD1:BitsPerSample": 14,
    "SubIFD1:ImageWidth": 6040,
    "SubIFD1:ImageHeight": 4032,
}
RANGES = (
    ("IFD0:StripOffsets", "IFD0:StripByteCounts"),
    ("SubIFD1:StripOffsets", "SubIFD1:StripByteCounts"),
    ("PreviewIFD:PreviewImageStart", "PreviewIFD:PreviewImageLength"),
    ("SubIFD:JpgFromRawStart", "SubIFD:JpgFromRawLength"),
    ("SubIFD2:OtherImageStart", "SubIFD2:OtherImageLength"),
)


def require_tested_nef(tool: ExifTool, path: Path) -> None:
    metadata = tool.metadata(path, *(f"-{tag}" for tag in PROFILE))
    if any(metadata.get(tag) != value for tag, value in PROFILE.items()):
        raise ValueError("NEF GPS supports only the verified Nikon Z 5 14-bit lossless profile")


@dataclass(frozen=True)
class NefFingerprint:
    metadata: dict[str, Any]
    payloads: tuple[str, ...]


def fingerprint_nef(tool: ExifTool, path: Path) -> NefFingerprint:
    """Hash exact compressed RAW, thumbnail and preview bytes, allowing relocation."""
    require_tested_nef(tool, path)
    fields = (
        *PROFILE,
        *(tag for pair in RANGES for tag in pair),
        "MakerNotes:all",
        "ExifIFD:all",
        "IFD0:Orientation",
        "validate",
        "warning",
        "error",
    )
    metadata = tool.metadata(path, *(f"-{tag}" for tag in fields))
    metadata.pop("SourceFile", None)
    payloads = []
    size = path.stat().st_size
    with path.open("rb") as source:
        for offset_tag, length_tag in RANGES:
            offset = metadata.pop(offset_tag, None)
            length = metadata.pop(length_tag, None)
            if (
                type(offset) is not int
                or type(length) is not int
                or offset < 0
                or length <= 0
                or offset + length > size
            ):
                raise ValueError(f"Invalid NEF payload range: {offset_tag}")
            digest = hashlib.sha256()
            source.seek(offset)
            remaining = length
            while remaining:
                block = source.read(min(remaining, 1024 * 1024))
                if not block:
                    raise OSError("NEF payload changed during verification")
                digest.update(block)
                remaining -= len(block)
            payloads.append(digest.hexdigest())
    return NefFingerprint(metadata, tuple(payloads))
