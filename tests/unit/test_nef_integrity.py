"""RAW compatibility is determined by container and preservation, not camera model."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from aim_tool.services.exiftool import ExifTool
from aim_tool.services.nef_gps import fingerprint_nef


class RawTool:
    def __init__(self, file_type: str, image_hash: str | None = "a" * 64) -> None:
        self.file_type = file_type
        self.image_hash = image_hash
        self.calls: list[tuple[str, ...]] = []
        self.diagnostics: dict[str, Any] = {"ExifTool:Validate": "0 0 0"}
        self.previews: dict[str, Any] = {"IFD0:ThumbnailImage": sha256(b"hello").hexdigest()}

    def metadata(self, path: Path, *tags: str) -> dict[str, Any]:
        self.calls.append(tags)
        if "-preview:all" in tags:
            return {"SourceFile": str(path), **self.previews}
        return {
            "SourceFile": str(path),
            "File:FileType": self.file_type,
            "IFD0:Make": "Any manufacturer",
            "IFD0:Model": "A camera not on a model whitelist",
            "IFD0:StripOffsets": 42,
            "File:ImageDataHash": self.image_hash,
            **self.diagnostics,
        }


def test_nef_does_not_require_a_camera_whitelist() -> None:
    tool = RawTool("NEF")
    fingerprint = fingerprint_nef(cast(ExifTool, tool), Path("photo.NEF"))
    assert fingerprint.metadata["IFD0:Model"] == "A camera not on a model whitelist"
    assert "IFD0:StripOffsets" not in fingerprint.metadata
    assert not any(key.startswith("ExifTool:") for key in fingerprint.metadata)
    assert "File:ImageDataHash" not in fingerprint.metadata
    assert fingerprint.previews == {"IFD0:ThumbnailImage": sha256(b"hello").hexdigest()}
    assert len(tool.calls) == 2
    assert "-validate" in tool.calls[0] and "-ImageDataHash" in tool.calls[0]
    assert "PrintConv=1" not in tool.calls[0]
    assert "PrintConv=1" in tool.calls[1]
    assert "Filter=require Digest::SHA; $_=Digest::SHA::sha256_hex($_)" in tool.calls[1]


@pytest.mark.parametrize("value", (None, "", "a" * 63, "A" * 64, "base64:aGVsbG8="))
def test_raw_preview_hashing_fails_closed(value: Any) -> None:
    tool = RawTool("NEF")
    tool.previews["IFD0:ThumbnailImage"] = value
    with pytest.raises(TypeError, match="preview data cannot be verified"):
        fingerprint_nef(cast(ExifTool, tool), Path("photo.NEF"))


def test_raw_duplicate_diagnostics_remain_part_of_the_fingerprint() -> None:
    tool = RawTool("NEF")
    tool.diagnostics.update(
        {"ExifTool:Warning": "First warning", "ExifTool:Copy1:Warning": "Second warning"}
    )
    fingerprint = fingerprint_nef(cast(ExifTool, tool), Path("photo.NEF"))
    assert fingerprint.diagnostics == {
        f"{'Warning':<32}: First warning",
        f"{'Warning':<32}: Second warning",
    }


@pytest.mark.parametrize("value", ("Bad container", None))
def test_raw_diagnostics_errors_fail_closed(value: Any) -> None:
    tool = RawTool("NEF")
    tool.diagnostics["ExifTool:Error"] = value
    with pytest.raises((ValueError, TypeError), match="RAW metadata"):
        fingerprint_nef(cast(ExifTool, tool), Path("photo.NEF"))
    assert len(tool.calls) == 1


@pytest.mark.parametrize("value", (None, "", "OK", "0 0", "1 0 0"))
def test_raw_validation_must_return_valid_error_warning_counts(value: Any) -> None:
    tool = RawTool("NEF")
    tool.diagnostics["ExifTool:Validate"] = value
    with pytest.raises(ValueError, match="RAW metadata"):
        fingerprint_nef(cast(ExifTool, tool), Path("photo.NEF"))
    assert len(tool.calls) == 1


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
