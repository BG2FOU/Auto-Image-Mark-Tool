"""S4 capture date behavior before table and watermark integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from aim_tool.domain.dates import DateError, parse_capture_date, resolve_capture_date


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024-02-29", date(2024, 2, 29)),
        ("2024/02/29", date(2024, 2, 29)),
        ("2024-02-29T23:59:59.123+14:00", date(2024, 2, 29)),
        ("2024:02:29 08:09:10", date(2024, 2, 29)),
        (datetime(2024, 2, 29, 23, 59, tzinfo=timezone(timedelta(hours=14))), date(2024, 2, 29)),
    ],
)
def test_capture_date_keeps_calendar_day(value: str | datetime, expected: date) -> None:
    assert parse_capture_date(value) == expected


@pytest.mark.parametrize(
    "value", ["2023-02-29", "01/02/2026", "2026-13-01", "today", "2026-01-01 09:00", "2026:01:01"]
)
def test_invalid_or_ambiguous_dates_are_rejected(value: str) -> None:
    with pytest.raises(DateError):
        parse_capture_date(value)


def test_date_priority_and_explicit_create_date_fallback() -> None:
    values = {
        "manual": "2026-10-01",
        "imported": "2026-09-30",
        "exif_datetime_original": "2026:09:29 23:59:59",
        "exif_create_date": "2026:09:28 00:00:00",
    }
    assert resolve_capture_date(**values).watermark_text == "2026/10/01"
    values["manual"] = ""
    assert resolve_capture_date(**values).source == "table"
    values["imported"] = ""
    assert resolve_capture_date(**values).source == "EXIF DateTimeOriginal"
    values["exif_datetime_original"] = ""
    with pytest.raises(DateError, match="missing"):
        resolve_capture_date(**values)
    assert resolve_capture_date(**values, allow_create_date=True).source == "EXIF CreateDate"


def test_invalid_explicit_date_does_not_silently_fall_back() -> None:
    with pytest.raises(DateError, match="Invalid calendar"):
        resolve_capture_date(manual="2026-02-30", imported="2026-03-01")
