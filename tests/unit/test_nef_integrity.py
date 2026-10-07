"""RAW compatibility is determined by container and preservation, not camera model."""

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from aim_tool.services.exiftool import ExifTool
from aim_tool.services.nef_gps import fingerprint_nef


class RawTool:
    def __init__(self, file_type: str, image_hash: str | None = "a" * 64) -> None:
        self.file_type = file_type
        self.image_hash = image_hash

    def metadata(self, path: Path, *tags: str) -> dict[str, Any]:
        if "-ImageDataHash" in tags:
            return {
                "SourceFile": str(path),
                "File:ImageDataHash": self.image_hash,
                "IFD0:ThumbnailImage": "base64:aGVsbG8=",
            }
        return {
            "SourceFile": str(path),
            "File:FileType": self.file_type,
            "IFD0:Make": "Any manufacturer",
            "IFD0:Model": "A camera not on a model whitelist",
            "IFD0:StripOffsets": 42,
        }

    def _run_for_path(self, path: Path, *tags: str) -> str:
        return "Validate : OK\n"


def test_nef_does_not_require_a_camera_whitelist() -> None:
    fingerprint = fingerprint_nef(cast(ExifTool, RawTool("NEF")), Path("photo.NEF"))
    assert fingerprint.metadata["IFD0:Model"] == "A camera not on a model whitelist"
    assert "IFD0:StripOffsets" not in fingerprint.metadata


@pytest.mark.parametrize(
    "image_hash",
    (None, "", "not-a-hash", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
)
def test_raw_without_a_verifiable_image_is_blocked(image_hash: str | None) -> None:
    with pytest.raises(ValueError, match="cannot be verified"):
        fingerprint_nef(cast(ExifTool, RawTool("NEF", image_hash)), Path("photo.NEF"))


def test_renamed_jpeg_is_not_accepted_as_raw() -> None:
    with pytest.raises(ValueError, match="Unsupported RAW container"):
        fingerprint_nef(cast(ExifTool, RawTool("JPEG")), Path("photo.NEF"))


def test_raw_preservation_detects_changes_and_allows_only_resolved_warnings() -> None:
    before = fingerprint_nef(cast(ExifTool, RawTool("NEF")), Path("photo.NEF"))
    warning = "Warning : A preexisting minor warning"
    warned = replace(before, diagnostics=frozenset({warning}))
    assert before.preserved_from(warned)
    assert not warned.preserved_from(before)
    for changed in (
        replace(before, image_hash="b" * 64),
        replace(before, previews={}),
        replace(before, metadata={}),
    ):
        assert not changed.preserved_from(before)
