"""NEF preservation checks reject unknown encodings and changed payloads."""

from pathlib import Path
from typing import Any, cast

import pytest

from aim_tool.services.exiftool import ExifTool
from aim_tool.services.nef_gps import PROFILE, RANGES, fingerprint_nef, require_tested_nef


class MetadataTool:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def metadata(self, path: Path, *tags: str) -> dict[str, Any]:
        return {"SourceFile": str(path), **self.values}


def _metadata() -> dict[str, Any]:
    values: dict[str, Any] = {**PROFILE, "Nikon:ShutterCount": 42}
    for index, (offset, length) in enumerate(RANGES):
        values[offset] = index * 8
        values[length] = 8
    return values


def test_nef_fingerprint_allows_relocation_but_detects_payload_and_makernote_changes(
    tmp_path: Path,
) -> None:
    original = tmp_path / "a.NEF"
    original.write_bytes(bytes(range(8 * len(RANGES))))
    source_values = _metadata()
    tool = cast(ExifTool, MetadataTool(source_values))
    before = fingerprint_nef(tool, original)
    relocated = tmp_path / "b.NEF"
    relocated.write_bytes(b"padding!" + original.read_bytes())
    moved = dict(source_values)
    for offset, _ in RANGES:
        moved[offset] += 8
    moved_tool = cast(ExifTool, MetadataTool(moved))
    assert fingerprint_nef(moved_tool, relocated) == before
    for offset, _ in RANGES:
        with relocated.open("r+b") as payload:
            payload.seek(moved[offset])
            payload.write(b"\xff")
        assert fingerprint_nef(moved_tool, relocated) != before
        relocated.write_bytes(b"padding!" + original.read_bytes())
    moved["Nikon:ShutterCount"] = 43
    assert fingerprint_nef(moved_tool, relocated) != before


@pytest.mark.parametrize(
    ("tag", "value"),
    (("IFD0:Model", "NIKON Z 6"), ("Nikon:NEFCompression", 1), ("SubIFD1:BitsPerSample", 12)),
)
def test_nef_unknown_camera_or_encoding_is_blocked(tag: str, value: Any) -> None:
    values = _metadata()
    values[tag] = value
    with pytest.raises(ValueError, match="verified Nikon Z 5"):
        require_tested_nef(cast(ExifTool, MetadataTool(values)), Path("a.NEF"))


@pytest.mark.parametrize(
    "offset,length", ((-1, 8), (0, 0), (8 * len(RANGES) - 2, 8), (None, 8), (0, True))
)
def test_nef_invalid_or_missing_payload_range_is_blocked(
    tmp_path: Path, offset: Any, length: Any
) -> None:
    source = tmp_path / "a.NEF"
    source.write_bytes(bytes(range(8 * len(RANGES))))
    values = _metadata()
    values[RANGES[0][0]] = offset
    values[RANGES[0][1]] = length
    with pytest.raises(ValueError, match="Invalid NEF payload range"):
        fingerprint_nef(cast(ExifTool, MetadataTool(values)), source)
