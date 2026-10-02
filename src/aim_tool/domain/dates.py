"""Capture-date parsing and explicit source precedence for watermark text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

type DateInput = str | date | datetime


class DateError(ValueError):
    """A date is missing, ambiguous, or is not a real calendar date."""


@dataclass(frozen=True)
class ResolvedDate:
    day: date
    source: str
    original: DateInput

    @property
    def watermark_text(self) -> str:
        return self.day.strftime("%Y/%m/%d")


_DATE = re.compile(r"\d{4}(?:-\d{2}-\d{2}|/\d{1,2}/\d{1,2})\Z")
_ISO_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\Z"
)
_EXIF_DATETIME = re.compile(r"\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?\Z")
_AMBIGUOUS = re.compile(r"\d{1,2}/\d{1,2}/\d{4}\Z")


def parse_capture_date(value: DateInput) -> date:
    """Keep the represented calendar day; never shift it through UTC."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise DateError("Capture date must be text or a date cell")
    text = value.strip()
    if _AMBIGUOUS.fullmatch(text):
        raise DateError(f"Ambiguous capture date: {text}; use YYYY-MM-DD")
    try:
        if _DATE.fullmatch(text):
            if "/" in text:
                year, month, day = (int(part) for part in text.split("/"))
                return date(year, month, day)
            return date.fromisoformat(text)
        if _ISO_DATETIME.fullmatch(text):
            normalized = text.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).date()
        if _EXIF_DATETIME.fullmatch(text):
            normalized = text[:10].replace(":", "-") + text[10:]
            return datetime.fromisoformat(normalized).date()
    except ValueError as error:
        raise DateError(f"Invalid calendar date: {text}") from error
    raise DateError(f"Unsupported capture date: {text}")


def resolve_capture_date(
    *,
    manual: DateInput | None = None,
    imported: DateInput | None = None,
    exif_datetime_original: DateInput | None = None,
    exif_create_date: DateInput | None = None,
    allow_create_date: bool = False,
) -> ResolvedDate:
    """Manual > table > DateTimeOriginal > explicitly allowed CreateDate."""
    candidates: tuple[tuple[str, DateInput | None], ...] = (
        ("manual", manual),
        ("table", imported),
        ("EXIF DateTimeOriginal", exif_datetime_original),
        ("EXIF CreateDate", exif_create_date if allow_create_date else None),
    )
    for source, original in candidates:
        if original is None or isinstance(original, str) and not original.strip():
            continue
        return ResolvedDate(parse_capture_date(original), source, original)
    raise DateError("Capture date is missing; enter a date or allow CreateDate fallback")
