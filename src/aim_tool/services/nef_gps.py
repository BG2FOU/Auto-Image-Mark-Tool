"""Verify Nikon NEF RAW contents and metadata across GPS edits without developing pixels."""

from __future__ import annotations

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

_PREVIEW_HASH_FILTER = "require Digest::SHA; $_=Digest::SHA::sha256_hex($_)"


def _metadata_diagnostics(metadata: dict[str, Any]) -> frozenset[str]:
    """Keep every duplicate diagnostic from a family-4-qualified JSON record."""
    counts = metadata.get("ExifTool:Validate")
    if not isinstance(counts, str) or re.fullmatch(r"[0-9]+ [0-9]+ [0-9]+", counts) is None:
        raise ValueError("RAW metadata diagnostics cannot be verified")
    if int(counts.split()[0]):
        raise ValueError("RAW metadata validation failed")
    diagnostics = set()
    for key, value in metadata.items():
        kind = key.split(":")[-1]
        if not key.startswith("ExifTool:") or kind not in {"Warning", "Error"}:
            continue
        if not isinstance(value, str):
            raise TypeError("RAW metadata diagnostics cannot be verified")
        # Match the legacy -s text representation, including its alignment.
        diagnostics.add(f"{kind:<32}: {value}".strip())
    if any(line.startswith("Error") for line in diagnostics):
        raise ValueError("RAW metadata validation failed")
    return frozenset(diagnostics)


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
        "-validate",
        "-warning",
        "-error",
        "-api",
        "ImageHashType=SHA256",
        "-ImageDataHash",
    )
    diagnostics = _metadata_diagnostics(metadata)
    detected = metadata.get("File:FileType")
    if detected != "NEF" or path.suffix.lower() != ".nef":
        raise ValueError("Unsupported RAW container or filename does not match its format")
    image_hash = metadata.pop("File:ImageDataHash", None)
    if (
        not isinstance(image_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", image_hash) is None
        or image_hash == hashlib.sha256(b"").hexdigest()
    ):
        raise ValueError("RAW image data cannot be verified; GPS output was blocked")
    for key in tuple(metadata):
        if (
            key == "SourceFile"
            or key.split(":")[-1] in RELOCATABLE
            or (
                key.startswith("ExifTool:")
                and key.split(":")[-1] in {"Validate", "Warning", "Error"}
            )
        ):
            metadata.pop(key)
    # Hash all preview bytes inside the pinned ExifTool process, avoiding the
    # multi-megabyte base64/JSON round trip. Filter applies only to PrintConv
    # values, so enable it solely for this preview-only request. The ordinary
    # metadata record above retains its numeric/unconverted representation.
    images = tool.metadata(
        path,
        "-G1:4",
        "-b",
        "-preview:all",
        "-api",
        "PrintConv=1",
        "-api",
        f"Filter={_PREVIEW_HASH_FILTER}",
    )
    images.pop("SourceFile", None)
    previews = {}
    for key, value in images.items():
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise TypeError("RAW preview data cannot be verified")
        previews[key] = value
    return NefFingerprint(metadata, image_hash, previews, diagnostics)


def require_tested_nef(tool: ExifTool, path: Path) -> None:
    """Retain the legacy API using per-file verification instead of a model whitelist."""
    fingerprint_nef(tool, path)
