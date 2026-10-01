"""Exercise the public GPS batch CLI against the pinned real ExifTool."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from aim_tool.services.exiftool import ExifTool, ExifToolError

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/batch_gps.py"


@pytest.fixture
def tool(pytestconfig: pytest.Config) -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(str(error))
        pytest.skip(str(error))


def _call(
    table: Path, input_root: Path, output_root: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--csv",
            str(table),
            "--input-root",
            str(input_root),
            "--output-root",
            str(output_root),
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )


def test_two_file_batch_preflight_execution_and_repeat_protection(
    tmp_path: Path, tool: ExifTool
) -> None:
    input_root = tmp_path / "input"
    nested = input_root / "中文 目录"
    nested.mkdir(parents=True)
    Image.new("RGB", (40, 30), (10, 20, 30)).save(nested / "甲.jpg")
    Image.new("RGB", (32, 24), (50, 60, 70)).save(input_root / "b.JPEG")
    table = tmp_path / "rows.csv"
    with table.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("file_name", "latitude", "longitude"))
        writer.writerow(("中文 目录/甲.jpg", "-24.123456789", "118.987654321"))
        writer.writerow(("b.JPEG", "0", "-180"))
    output_root = tmp_path / "output"
    preview = _call(table, input_root, output_root)
    assert preview.returncode == 0, preview.stderr
    assert not output_root.exists()

    report = tmp_path / "report.json"
    result = _call(table, input_root, output_root, "--execute", "--report", str(report))
    assert result.returncode == 0, result.stderr
    assert "success:" in result.stdout
    assert "latitude" not in report.read_text(encoding="utf-8")
    first = tool.read_gps(output_root / "中文 目录/甲.jpg")
    second = tool.read_gps(output_root / "b.JPEG")
    assert first is not None and second is not None
    assert abs(first.latitude + 24.123456789) <= 1e-6
    assert abs(first.longitude - 118.987654321) <= 1e-6
    assert second.latitude == 0
    assert second.longitude == -180

    repeat = _call(table, input_root, output_root, "--execute")
    assert repeat.returncode == 2
    assert "Output already exists" in repeat.stderr


def test_duplicate_rows_stop_before_any_write(tmp_path: Path, tool: ExifTool) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    Image.new("RGB", (16, 16)).save(input_root / "one.jpg")
    table = tmp_path / "duplicates.csv"
    table.write_text("file_name,latitude,longitude\none.jpg,1,2\nONE.jpg,3,4\n", encoding="utf-8")
    output_root = tmp_path / "output"
    result = _call(table, input_root, output_root, "--execute")
    assert result.returncode == 2
    assert "Duplicate file_name" in result.stderr
    assert not output_root.exists()
