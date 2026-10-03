"""Pinned ExifTool subprocess adapter for GPS metadata."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from aim_tool.domain.validation import validate_altitude
from aim_tool.domain.validation import validate_coordinates as _validate_coordinates

VERSION = "13.59"
ROOT = Path(__file__).resolve().parents[3]
_WINDOWS_SPAWN_LOCK = Lock()


class ExifToolError(RuntimeError):
    """ExifTool is unavailable or returned an invalid result."""


@dataclass(frozen=True)
class GpsCoordinates:
    latitude: float
    longitude: float
    altitude: float = 0.0


def validate_coordinates(latitude: float, longitude: float) -> None:
    """Preserve the ExifTool adapter's public validator API."""
    _validate_coordinates(latitude, longitude)


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


def _windows_ansi_directory(directory: Path) -> Path | None:
    """Return a lossless ANSI path, using an existing DOS alias when needed."""
    if sys.platform != "win32":
        raise OSError("Windows path compatibility requires Windows")
    import ctypes

    try:
        str(directory).encode("mbcs")
        return directory
    except UnicodeEncodeError:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        kernel.GetShortPathNameW.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(32768)
        size = kernel.GetShortPathNameW(str(directory), buffer, len(buffer))
        if not 0 < size < len(buffer):
            return None
        try:
            buffer.value.encode("mbcs")
        except UnicodeEncodeError:
            return None
        # Do not resolve this alias: resolving would restore the incompatible name.
        return Path(buffer.value)


def _run_frozen_windows(
    command: list[str], directory: Path | None, input_text: str | None, timeout: int
) -> subprocess.CompletedProcess[str]:
    """Spawn Perl with its own DLLs, then immediately restore the GUI DLL path."""
    if sys.platform != "win32":
        raise OSError("Windows helper spawning requires Windows")
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
    kernel.GetDllDirectoryW.restype = ctypes.c_uint
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    environment = os.environ.copy()
    bundle = Path(getattr(sys, "_MEIPASS", ROOT)).resolve()
    environment["PATH"] = os.pathsep.join(
        item
        for item in environment.get("PATH", "").split(os.pathsep)
        if item and not Path(item).resolve().is_relative_to(bundle)
    )
    with _WINDOWS_SPAWN_LOCK:
        size = kernel.GetDllDirectoryW(0, None)
        buffer = ctypes.create_unicode_buffer(size + 1)
        kernel.GetDllDirectoryW(len(buffer), buffer)
        original = buffer.value or None
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            process = subprocess.Popen(
                command,
                cwd=directory,
                env=environment,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        finally:
            kernel.SetDllDirectoryW(original)
    try:
        output, errors = process.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, output, errors)


class ExifTool:
    def __init__(self, executable: Path | None = None, timeout: int = 90) -> None:
        self.executable = (executable or _default_executable()).resolve()
        self.timeout = timeout
        self._support_directory: Path | None = None
        self._runtime_temporary: tempfile.TemporaryDirectory[str] | None = None
        if not self.executable.is_file():
            raise ExifToolError(f"ExifTool is missing: {self.executable}")
        try:
            version = self._run("-ver").strip()
            if version != VERSION:
                raise ExifToolError(f"Expected ExifTool {VERSION}, got {version}")
        except Exception:
            if self._runtime_temporary is not None:
                self._runtime_temporary.cleanup()
            raise

    def _windows_runtime_directory(self, support: Path) -> Path:
        if self._support_directory is not None:
            return self._support_directory
        compatible = _windows_ansi_directory(support)
        if compatible is not None:
            self._support_directory = compatible
            return compatible
        # Perl 5.32 maps even relative opens through its ANSI working directory.
        # Volumes without DOS aliases need an unchanged copy in a private temp dir.
        parents = [Path(tempfile.gettempdir())]
        if local_data := os.environ.get("LOCALAPPDATA"):
            parents.append(Path(local_data))
        for parent in parents:
            compatible = _windows_ansi_directory(parent)
            if compatible is None:
                continue
            try:
                temporary = tempfile.TemporaryDirectory(prefix="aim-exiftool-", dir=compatible)
            except OSError:
                continue
            self._runtime_temporary = temporary
            directory = Path(temporary.name) / "exiftool_files"
            try:
                shutil.copytree(support, directory)
            except OSError as error:
                temporary.cleanup()
                raise ExifToolError(f"Cannot stage bundled ExifTool runtime: {error}") from error
            self._support_directory = directory
            return directory
        raise ExifToolError(
            "Bundled Perl needs a temporary directory representable in the Windows "
            "system code page. Set TEMP to a writable directory with an ASCII path."
        )

    def _run(
        self,
        *arguments: str,
        argfile_input: str | None = None,
        reject_warnings: bool = False,
    ) -> str:
        command = (
            ["perl", str(self.executable), *arguments]
            if self.executable.suffix.lower() != ".exe" and sys.platform != "win32"
            else [str(self.executable), *arguments]
        )
        working_directory = None
        if sys.platform == "win32" and self.executable.suffix.lower() == ".exe":
            support = self.executable.parent / "exiftool_files"
            interpreter = support / "perl.exe"
            if interpreter.is_file() and (support / "exiftool.pl").is_file():
                # The launcher and Perl's virtual working directory use ANSI paths.
                working_directory = self._windows_runtime_directory(support)
                command = [str(working_directory / "perl.exe"), "-Ilib", "exiftool.pl", *arguments]
        try:
            if sys.platform == "win32" and getattr(sys, "frozen", False):
                completed = _run_frozen_windows(
                    command, working_directory, argfile_input, self.timeout
                )
            else:
                completed = subprocess.run(
                    command,
                    cwd=working_directory,
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
        if reject_warnings and completed.stderr.strip():
            raise ExifToolError(f"ExifTool metadata warning: {completed.stderr.strip()}")
        return completed.stdout

    def _run_for_path(self, path: Path, *arguments: str) -> str:
        filename = str(path.resolve())
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
            "-GPS:GPSAltitude",
            "-GPS:GPSAltitudeRef",
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
        altitude = values.get("GPS:GPSAltitude", 0)
        altitude_ref = values.get("GPS:GPSAltitudeRef", 0)
        if ("GPS:GPSAltitude" in values) != ("GPS:GPSAltitudeRef" in values):
            raise ExifToolError("GPS altitude fields are incomplete")
        if (
            type(altitude) not in {int, float}
            or altitude < 0
            or type(altitude_ref) is not int
            or altitude_ref not in {0, 1}
        ):
            raise ExifToolError("GPS altitude fields are invalid")
        signed_altitude = float(altitude) * (-1 if altitude_ref == 1 else 1)
        validate_altitude(signed_altitude)
        return GpsCoordinates(signed_latitude, signed_longitude, signed_altitude)

    def has_auxiliary_gps(self, path: Path) -> bool:
        values = self.metadata(path, "-gps:all")
        ordinary = {
            "SourceFile",
            "GPS:GPSVersionID",
            "GPS:GPSAltitude",
            "GPS:GPSAltitudeRef",
            "GPS:GPSLatitude",
            "GPS:GPSLatitudeRef",
            "GPS:GPSLongitude",
            "GPS:GPSLongitudeRef",
        }
        return any(key not in ordinary for key in values)

    def write_gps(
        self, path: Path, latitude: float, longitude: float, altitude: float = 0.0
    ) -> None:
        validate_coordinates(latitude, longitude)
        validate_altitude(altitude)
        args = (
            "-overwrite_original",
            "-P",
            "-GPS:all=",
            f"-GPS:GPSLatitude={abs(latitude):.12f}",
            f"-GPS:GPSLatitudeRef={'S' if latitude < 0 else 'N'}",
            f"-GPS:GPSLongitude={abs(longitude):.12f}",
            f"-GPS:GPSLongitudeRef={'W' if longitude < 0 else 'E'}",
            f"-GPS:GPSAltitude={abs(altitude):.6f}",
            f"-GPS:GPSAltitudeRef#={1 if altitude < 0 else 0}",
        )
        self._run_for_path(path, *args)
        readback = self.read_gps(path)
        if readback is None or (
            abs(readback.latitude - latitude) > 1e-6
            or abs(readback.longitude - longitude) > 1e-6
            or abs(readback.altitude - altitude) > 1e-4
        ):
            raise ExifToolError("GPS readback differs from requested coordinates")

    def copy_tags(
        self,
        source: Path,
        target: Path,
        tags: tuple[str, ...],
        overrides: Mapping[str, int],
    ) -> None:
        """Copy named tags between distinct files using a UTF-8 argument stream."""
        source = source.resolve()
        target = target.resolve()
        if source == target or not source.is_file() or not target.is_file():
            raise ExifToolError("Metadata transfer requires two distinct existing files")
        names = (*tags, *overrides)
        if not names or any(
            re.fullmatch(r"[A-Za-z0-9-]+:[A-Za-z0-9-]+", tag) is None for tag in names
        ):
            raise ExifToolError("Invalid metadata tag selection")
        if any(type(value) is not int for value in overrides.values()):
            raise ExifToolError("Metadata overrides must be integers")
        if any("\n" in str(path) or "\r" in str(path) for path in (source, target)):
            raise ExifToolError("File path cannot contain a newline")
        arguments = [
            "-overwrite_original",
            "-P",
            "-n",
            *(["-tagsFromFile", str(source)] if tags else []),
            *(f"-{tag}" for tag in tags),
            *(f"-{tag}={value}" for tag, value in overrides.items()),
            str(target),
        ]
        self._run(
            "-charset",
            "filename=UTF8",
            "-@",
            "-",
            argfile_input="\n".join(arguments) + "\n",
            reject_warnings=True,
        )
