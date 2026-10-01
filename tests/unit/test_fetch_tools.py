"""S1 tool archive validation tests."""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from fetch_tools import ToolInstallError, extract_runtime, verify_archive


def test_archive_hash_is_checked(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"archive")
    verify_archive(archive, hashlib.sha256(b"archive").hexdigest())
    with pytest.raises(ToolInstallError, match="SHA-256 mismatch"):
        verify_archive(archive, "0" * 64)


def test_extracts_executable_and_support_files(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("exiftool-13.59_64/exiftool(-k).exe", b"test executable")
        zipped.writestr("exiftool-13.59_64/exiftool_files/module.dat", b"test module")
    target = tmp_path / "exiftool"
    extract_runtime(archive, target, "exiftool_files")
    assert (target / "exiftool.exe").read_bytes() == b"test executable"
    assert (target / "exiftool_files/module.dat").read_bytes() == b"test module"


def test_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../exiftool(-k).exe", b"bad")
        zipped.writestr("exiftool_files/module.dat", b"module")
    with pytest.raises(ToolInstallError, match="Unsafe path"):
        extract_runtime(archive, tmp_path / "target", "exiftool_files")
