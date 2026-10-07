"""EXIF capture time supplies the NEF GPS date without file-time fallbacks."""

from typing import Any

import pytest

from aim_tool.services.exiftool import ExifToolError, _gps_capture_timestamp


@pytest.mark.parametrize(
    ("original", "offset", "subsecond", "expected"),
    (
        ("2026:01:01 04:43:20", "+08:00", 45, ("2025:12:31", "20:43:20.45")),
        ("2026:12:31 23:59:59", "-03:30", "007", ("2027:01:01", "03:29:59.007")),
        ("2026:05:27 04:43:20", None, "", ("2026:05:27", "04:43:20")),
        ("2026:05:27 04:43:20", "+00:00", 0, ("2026:05:27", "04:43:20")),
    ),
)
def test_gps_date_uses_capture_time_and_its_offset(
    original: str, offset: str | None, subsecond: str | int, expected: tuple[str, str]
) -> None:
    values: dict[str, Any] = {
        "ExifIFD:DateTimeOriginal": original,
        "ExifIFD:SubSecTimeOriginal": subsecond,
    }
    if offset is not None:
        values["ExifIFD:OffsetTimeOriginal"] = offset
    assert _gps_capture_timestamp(values) == expected


def test_missing_capture_time_does_not_use_create_date_or_file_time() -> None:
    assert _gps_capture_timestamp({"ExifIFD:CreateDate": "2026:05:27 04:43:20"}) is None


@pytest.mark.parametrize(
    ("tag", "value"),
    (
        ("DateTimeOriginal", "2026:02:30 12:00:00"),
        ("DateTimeOriginal", 2026),
        ("OffsetTimeOriginal", "+24:00"),
        ("OffsetTimeOriginal", "+08:60"),
        ("OffsetTimeOriginal", "invalid"),
        ("SubSecTimeOriginal", "invalid"),
    ),
)
def test_invalid_capture_time_is_rejected(tag: str, value: Any) -> None:
    values = {"ExifIFD:DateTimeOriginal": "2026:05:27 04:43:20", f"ExifIFD:{tag}": value}
    with pytest.raises(ExifToolError, match="Invalid EXIF capture time"):
        _gps_capture_timestamp(values)
