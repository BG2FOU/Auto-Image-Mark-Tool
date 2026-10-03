"""Shared checks for row edits, table previews and workflow inputs."""

from __future__ import annotations

import math
import re


def validate_coordinates(latitude: float, longitude: float) -> None:
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("Coordinates must be finite WGS84 decimal degrees")


def validate_watermark_fields(category: str | None, subject: str | None) -> None:
    if category is None and subject is None:
        return
    if category not in {"aviation", "railway", "landscape"}:
        raise ValueError("Unsupported watermark category")
    if not subject or not subject.strip() or any(char in subject for char in "\r\n\t"):
        raise ValueError("Missing or invalid watermark subject")
    if category in {"aviation", "railway"} and re.fullmatch(r"[A-Z0-9-]+", subject) is None:
        raise ValueError("Invalid aviation/railway subject")


def validate_altitude(altitude: float) -> None:
    if type(altitude) not in {int, float} or not math.isfinite(altitude):
        raise ValueError("Altitude must be finite metres above or below sea level")
