"""Verify Nikon NEF RAW contents and metadata across GPS edits without developing pixels."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aim_tool.services.exiftool import ExifTool

# These pointers may move when ExifTool rebuilds the container. Their referenced
# image contents are checked by ImageDataHash and the extracted preview hashes.
RELOCATABLE = frozenset(
    {
        "StripOffsets",
        "TileOffsets",
        "ThumbnailOffset",
        "PreviewImageStart",
        "JpgFromRawStart",
        "OtherImageStart",
        "PreviewTIFFStart",
        "ThumbnailTIFFStart",
        "PreviewImageOffset",
        "MakerNoteOffset",
        "RawImageOffset",
        "RawImageStart",
    }
)


def raw_diagnostics(tool: ExifTool, path: Path) -> frozenset[str]:
    result = tool._run_for_path(path, "-validate", "-a", "-warning", "-error", "-s")
    diagnostics = frozenset(
        line.strip() for line in result.splitlines() if re.match(r"^(Warning|Error)\s*:", line)
    )
    if any(line.startswith("Error") for line in diagnostics):
        raise ValueError("RAW metadata validation failed")
    return diagnostics


@dataclass(frozen=True)
class NefFingerprint:
    metadata: dict[str, Any]
    image_hash: str
    previews: dict[str, str]
    diagnostics: frozenset[str]

    def preserved_from(self, before: NefFingerprint) -> bool:
        return (
            self.metadata == before.metadata
            and self.image_hash == before.image_hash
            and self.previews == before.previews
            and self.diagnostics <= before.diagnostics
        )


def fingerprint_nef(tool: ExifTool, path: Path) -> NefFingerprint:
    """Fail closed if format identification or the main image hash is unavailable."""
    metadata = tool.metadata(
        path,
        "-G1:4",
        "-FileType",
        "-EXIF:all",
        "-MakerNotes:all",
        "-XMP:all",
        "-IPTC:all",
        "-ICC_Profile:all",
        "--GPS:all",
    )
    detected = metadata.get("File:FileType")
    if detected != "NEF" or path.suffix.lower() != ".nef":
        raise ValueError("Unsupported RAW container or filename does not match its format")
    for key in tuple(metadata):
        if key == "SourceFile" or key.split(":")[-1] in RELOCATABLE:
            metadata.pop(key)
    images = tool.metadata(
        path,
        "-G1:4",
        "-b",
        "-api",
        "ImageHashType=SHA256",
        "-ImageDataHash",
        "-preview:all",
    )
    image_hash = images.pop("File:ImageDataHash", None)
    if (
        not isinstance(image_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", image_hash) is None
        or image_hash == hashlib.sha256(b"").hexdigest()
    ):
        raise ValueError("RAW image data cannot be verified; GPS output was blocked")
    images.pop("SourceFile", None)
    previews = {}
    for key, value in images.items():
        if not isinstance(value, str):
            raise TypeError("RAW preview data cannot be verified")
        data = (
            base64.b64decode(value[7:], validate=True)
            if value.startswith("base64:")
            else value.encode()
        )
        previews[key] = hashlib.sha256(data).hexdigest()
    return NefFingerprint(metadata, image_hash, previews, raw_diagnostics(tool, path))


def require_tested_nef(tool: ExifTool, path: Path) -> None:
    """Retain the legacy API using per-file verification instead of a model whitelist."""
    fingerprint_nef(tool, path)
