"""Fetch the pinned Windows ExifTool archive and install its complete runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


class ToolInstallError(RuntimeError):
    """The pinned tool could not be installed safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise ToolInstallError(f"ExifTool archive not found: {path}")
    actual = sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        raise ToolInstallError(f"ExifTool SHA-256 mismatch: {path}")


def safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if not members:
        raise ToolInstallError("ExifTool archive is empty")
    for member in members:
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        mode = member.external_attr >> 16
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or ":" in path.parts[0]
            or stat.S_ISLNK(mode)
        ):
            raise ToolInstallError(f"Unsafe path in ExifTool archive: {name}")
    return members


def extract_runtime(archive_path: Path, destination: Path, support_dir: str) -> None:
    """Extract one EXE and its adjacent support tree without trusting archive paths."""
    with zipfile.ZipFile(archive_path) as archive:
        members = safe_members(archive)
        exe_names = {"exiftool(-k).exe", "exiftool.exe"}
        executables = [
            member for member in members if PurePosixPath(member.filename).name.lower() in exe_names
        ]
        if len(executables) != 1:
            raise ToolInstallError("Expected exactly one ExifTool executable")
        executable = executables[0]
        parent = PurePosixPath(executable.filename).parent
        support_prefix = str(parent / support_dir).rstrip("/") + "/"
        support = [member for member in members if member.filename.startswith(support_prefix)]
        if not support:
            raise ToolInstallError(f"Missing adjacent {support_dir} directory")

        destination.mkdir(parents=True, exist_ok=False)
        with (
            archive.open(executable) as source,
            (destination / "exiftool.exe").open("wb") as exe_output,
        ):
            shutil.copyfileobj(source, exe_output)
        for member in support:
            relative = PurePosixPath(member.filename).relative_to(parent)
            target = destination.joinpath(*relative.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def download_archive(url: str, destination: Path) -> None:
    if not url.startswith("https://"):
        raise ToolInstallError("ExifTool URL must use HTTPS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=45) as response, temporary.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ToolInstallError("ExifTool archive exceeds the size limit")
                output.write(chunk)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def install(manifest_path: Path, supplied_archive: Path | None = None) -> Path:
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ToolInstallError("Unsupported toolchain manifest schema")
    tool: dict[str, str] = manifest["exiftool"]
    if tool["platform"] != "windows-x64" or tool["install_dir"] != "tools/exiftool":
        raise ToolInstallError("Unexpected ExifTool platform or install directory")
    if tool["support_dir"] != "exiftool_files" or tool["executable"] != "exiftool.exe":
        raise ToolInstallError("Unexpected ExifTool runtime layout")
    destination = ROOT / tool["install_dir"]
    marker = destination / "install.json"
    if destination.exists():
        if (
            marker.is_file()
            and json.loads(marker.read_text(encoding="utf-8"))
            == {
                "version": tool["version"],
                "sha256": tool["sha256"],
            }
            and (destination / "exiftool.exe").is_file()
            and (destination / "exiftool_files").is_dir()
        ):
            return destination / "exiftool.exe"
        raise ToolInstallError(
            f"Existing ExifTool directory is not the pinned install: {destination}"
        )

    archive = supplied_archive or ROOT / "tools/downloads" / tool["archive_name"]
    if not archive.exists():
        if supplied_archive is not None:
            raise ToolInstallError(f"Offline archive not found: {archive}")
        download_archive(tool["url"], archive)
    verify_archive(archive, tool["sha256"])

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="exiftool-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "runtime"
        extract_runtime(archive, staged, tool["support_dir"])
        (staged / "install.json").write_text(
            json.dumps({"version": tool["version"], "sha256": tool["sha256"]}) + "\n",
            encoding="utf-8",
        )
        staged.rename(destination)
    return destination / "exiftool.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "packaging/toolchain.json")
    parser.add_argument("--archive", type=Path, help="verified local ZIP for offline installation")
    args = parser.parse_args()
    try:
        installed = install(args.manifest, args.archive)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ToolInstallError) as error:
        print(f"ExifTool install failed: {error}", file=sys.stderr)
        return 1
    print(installed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
