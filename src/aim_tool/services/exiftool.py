"""Pinned ExifTool subprocess adapter for GPS metadata."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION = "13.59"
ROOT = Path(__file__).resolve().parents[3]


class ExifToolError(RuntimeError):
    """ExifTool is unavailable or returned an invalid result."""


@dataclass(frozen=True)
class GpsCoordinates:
    latitude: float
    longitude: float


def validate_coordinates(latitude: float, longitude: float) -> None:
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("Coordinates must be finite WGS84 decimal degrees")


def _default_executable() -> Path:
    configured = os.environ.get("AIM_EXIFTOOL")
    if configured:
        return Path(configured).expanduser().resolve()
    bundle = Path(getattr(sys, "_MEIPASS", ROOT))
    if sys.platform == "win32":
        bundled = bundle / "tools/exiftool/exiftool.exe"
        if bundled.is_file():
            return bundled
        return ROOT / "tools/exiftool/exiftool.exe"
    bundled = bundle / "tools/exiftool-13.59/exiftool"
    if bundled.is_file():
        return bundled
    return ROOT / "tools/exiftool-13.59/exiftool"


class ExifTool:
    def __init__(self, executable: Path | None = None, timeout: int = 90) -> None:
        self.executable = (executable or _default_executable()).resolve()
        self.timeout = timeout
        if not self.executable.is_file():
            raise ExifToolError(f"ExifTool is missing: {self.executable}")
        version = self._run("-ver").strip()
        if version != VERSION:
            raise ExifToolError(f"Expected ExifTool {VERSION}, got {version}")

    def _run(self, *arguments: str, argfile_input: str | None = None) -> str:
        command = (
            ["perl", str(self.executable), *arguments]
            if self.executable.suffix.lower() != ".exe" and sys.platform != "win32"
            else [str(self.executable), *arguments]
        )
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                input=argfile_input,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ExifToolError(f"ExifTool failed to start or timed out: {error}") from error
        if completed.returncode != 0:
            raise ExifToolError(
                f"ExifTool exited {completed.returncode}: {completed.stderr.strip()}"
            )
        return completed.stdout

    def _run_for_path(self, path: Path, *arguments: str) -> str:
        filename = str(path)
        if "\r" in filename or "\n" in filename:
            raise ExifToolError("File path cannot contain a newline")
        return self._run(
            *arguments,
            "-charset",
            "filename=UTF8",
            "-@",
            "-",
            argfile_input=f"{filename}\n",
        )

    def metadata(self, path: Path, *tags: str) -> dict[str, Any]:
        output = self._run_for_path(path, "-j", "-n", "-G1", "-a", *tags)
        try:
            records: Any = json.loads(output)
        except json.JSONDecodeError as error:
            raise ExifToolError("ExifTool returned invalid JSON") from error
        if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
            raise ExifToolError("ExifTool returned an unexpected record count")
        return records[0]

    def read_gps(self, path: Path) -> GpsCoordinates | None:
        values = self.metadata(
            path,
            "-GPS:GPSLatitude",
            "-GPS:GPSLatitudeRef",
            "-GPS:GPSLongitude",
            "-GPS:GPSLongitudeRef",
        )
        keys = (
            "GPS:GPSLatitude",
            "GPS:GPSLatitudeRef",
            "GPS:GPSLongitude",
            "GPS:GPSLongitudeRef",
        )
        if all(key not in values for key in keys):
            return None
        if any(key not in values for key in keys):
            raise ExifToolError("GPS fields are incomplete")
        latitude = values[keys[0]]
        longitude = values[keys[2]]
        latitude_ref = values[keys[1]]
        longitude_ref = values[keys[3]]
        if (
            type(latitude) not in {int, float}
            or type(longitude) not in {int, float}
            or latitude_ref not in {"N", "S"}
            or longitude_ref not in {"E", "W"}
        ):
            raise ExifToolError("GPS fields have invalid types or directions")
        signed_latitude = float(latitude) * (-1 if latitude_ref == "S" else 1)
        signed_longitude = float(longitude) * (-1 if longitude_ref == "W" else 1)
        validate_coordinates(signed_latitude, signed_longitude)
        return GpsCoordinates(signed_latitude, signed_longitude)

    def has_auxiliary_gps(self, path: Path) -> bool:
        values = self.metadata(path, "-gps:all")
        ordinary = {
            "SourceFile",
            "GPS:GPSVersionID",
            "GPS:GPSLatitude",
            "GPS:GPSLatitudeRef",
            "GPS:GPSLongitude",
            "GPS:GPSLongitudeRef",
        }
        return any(key not in ordinary for key in values)

    def write_gps(self, path: Path, latitude: float, longitude: float) -> None:
        validate_coordinates(latitude, longitude)
        args = (
            "-overwrite_original",
            "-P",
            "-GPS:all=",
            f"-GPS:GPSLatitude={abs(latitude):.12f}",
            f"-GPS:GPSLatitudeRef={'S' if latitude < 0 else 'N'}",
            f"-GPS:GPSLongitude={abs(longitude):.12f}",
            f"-GPS:GPSLongitudeRef={'W' if longitude < 0 else 'E'}",
        )
        self._run_for_path(path, *args)
        readback = self.read_gps(path)
        if readback is None or (
            abs(readback.latitude - latitude) > 1e-6 or abs(readback.longitude - longitude) > 1e-6
        ):
            raise ExifToolError("GPS readback differs from requested coordinates")
