"""GPS page behavior with synthetic JPEGs and the real ExifTool adapter."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from pytestqt.qtbot import QtBot

from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.ui.gps_window import GpsWindow


def _jpeg(path: Path) -> None:
    image = QImage(32, 24, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    assert image.save(str(path), "JPEG")


@pytest.fixture
def tool() -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        pytest.skip(str(error))


def test_gps_page_preflight_and_batch_write(qtbot: QtBot, tmp_path: Path, tool: ExifTool) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    first = input_root / "甲.jpg"
    second = input_root / "b.JPEG"
    _jpeg(first)
    _jpeg(second)
    hashes = {path: sha256(path.read_bytes()).digest() for path in (first, second)}
    window = GpsWindow()
    qtbot.addWidget(window)
    window.show()
    window.add_photos((first, second), import_root=input_root)
    output_root = tmp_path / "output"
    window.output_root_edit.setText(str(output_root))
    window.bulk_latitude.setText("-24.123456789")
    window.bulk_longitude.setText("118.987654321")
    window.apply_button.click()
    assert window.preflight() is not None
    assert not output_root.exists()
    assert not window.watermark_button.isEnabled()

    window.run_button.click()
    qtbot.waitUntil(lambda: window._worker is None, timeout=20000)
    assert window.progress.value() == 2
    for source in (first, second):
        result = output_root / source.name
        gps = tool.read_gps(result)
        assert gps is not None
        assert abs(gps.latitude + 24.123456789) <= 1e-6
        assert abs(gps.longitude - 118.987654321) <= 1e-6
        assert sha256(source.read_bytes()).digest() == hashes[source]
    assert "批次完成：成功 2 / 2" in window.log.toPlainText()


def test_bad_coordinate_rejects_full_batch_before_write(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "one.jpg"
    _jpeg(source)
    window = GpsWindow()
    qtbot.addWidget(window)
    window.add_photos((source,))
    window.output_root_edit.setText(str(tmp_path / "output"))
    window._item(0, 2).setText("91")
    window._item(0, 3).setText("0")
    assert window.preflight() is None
    assert not (tmp_path / "output").exists()
    assert "坐标无效" in window.log.toPlainText()


def test_nef_row_remains_blocked_until_viewer_approval(
    qtbot: QtBot, tmp_path: Path, tool: ExifTool
) -> None:
    source = tmp_path / "one.NEF"
    source.write_bytes(b"diagnostic placeholder")
    window = GpsWindow()
    window._tool = tool
    qtbot.addWidget(window)
    window.add_photos((source,))
    window.output_root_edit.setText(str(tmp_path / "output"))
    window._item(0, 2).setText("0")
    window._item(0, 3).setText("0")
    assert window.preflight() is None
    assert "independent Nikon viewer approval" in window.log.toPlainText()
    assert not (tmp_path / "output").exists()
