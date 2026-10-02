"""Coordinate preset persistence and GPS page interaction."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog
from pytestqt.qtbot import QtBot

from aim_tool.domain import LocationPreset
from aim_tool.services.storage import ConfigStore
from aim_tool.ui import location_panel
from aim_tool.ui.gps_window import GpsWindow
from aim_tool.ui.location_panel import LocationDialog


def _jpeg(path: Path) -> None:
    image = QImage(16, 12, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    assert image.save(str(path), "JPEG")


def test_location_gui_crud_search_and_apply(qtbot: QtBot, tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "locations.json")
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    _jpeg(first)
    _jpeg(second)
    window = GpsWindow(location_store=store)
    qtbot.addWidget(window)
    window.add_photos((first, second))
    window._item(1, 0).setCheckState(Qt.CheckState.Unchecked)

    def fill_add_dialog() -> None:
        dialog = QApplication.activeModalWidget()
        assert dialog is not None
        dialog.name_edit.setText("厦门")
        dialog.latitude_edit.setText("24.478123")
        dialog.longitude_edit.setText("118.085456")
        dialog._validate_and_accept()

    QTimer.singleShot(0, fill_add_dialog)
    window.location_panel.new_button.click()
    assert store.path.is_file()
    original = store.load().locations[0]
    assert original.name == "厦门"
    assert window.location_panel.location_combo.count() == 1
    window.location_panel.search_edit.setText("不存在")
    assert window.location_panel.location_combo.count() == 0
    window.location_panel.search_edit.clear()
    window.location_panel.apply_button.click()
    assert window._item(0, 2).text() == "24.478123"
    assert window._item(0, 3).text() == "118.085456"
    assert window._item(1, 2).text() == ""

    def fill_edit_dialog() -> None:
        dialog = QApplication.activeModalWidget()
        assert dialog is not None
        dialog.name_edit.setText("海沧")
        dialog.latitude_edit.setText("24.5")
        dialog._validate_and_accept()

    QTimer.singleShot(0, fill_edit_dialog)
    window.location_panel.edit_button.click()
    edited = store.load().locations[0]
    assert edited.id == original.id
    assert edited.name == "海沧"
    assert edited.latitude == 24.5
    reopened = GpsWindow(location_store=store)
    qtbot.addWidget(reopened)
    assert reopened.location_panel.selected_location() == edited
    reopened.location_panel.delete_button.click()
    assert store.load().locations == ()
    assert not reopened.location_panel.apply_button.isEnabled()


def test_corrupt_list_is_not_overwritten(qtbot: QtBot, tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "locations.json")
    store.path.write_text("broken", encoding="utf-8")
    window = GpsWindow(location_store=store)
    qtbot.addWidget(window)
    assert "坐标列表无法读取" in window.log.toPlainText()
    window.location_panel.save_location(LocationPreset("test", 0, 0))
    assert store.path.read_text(encoding="utf-8") == "broken"
    assert "保存坐标失败" in window.log.toPlainText()


def test_frozen_windows_uses_exe_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = tmp_path / "portable" / "AutoImageMarkGpsGui.exe"
    monkeypatch.setattr(
        location_panel,
        "sys",
        SimpleNamespace(platform="win32", frozen=True, executable=str(executable)),
    )
    assert location_panel.default_location_store().path == executable.parent / "locations.json"


def test_dialog_rejects_invalid_coordinates(qtbot: QtBot) -> None:
    parent = GpsWindow()
    qtbot.addWidget(parent)
    dialog = LocationDialog(parent)
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("Bad")
    dialog.latitude_edit.setText("91")
    dialog.longitude_edit.setText("0")
    dialog._validate_and_accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "坐标无效" in dialog.error_label.text()


def test_location_import_export_preserves_ids(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ConfigStore(tmp_path / "locations.json")
    source = ConfigStore(tmp_path / "source.json")
    preset = LocationPreset("厦门", 24.4, 118.0)
    source.put_location(preset)
    window = GpsWindow(location_store=store)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        location_panel.QFileDialog, "getOpenFileName", lambda *args: (str(source.path), "")
    )
    window.location_panel.import_button.click()
    assert store.load().locations == (preset,)
    window.location_panel.import_button.click()
    assert store.load().locations == (preset,)
    destination = tmp_path / "export.json"
    monkeypatch.setattr(
        location_panel.QFileDialog, "getSaveFileName", lambda *args: (str(destination), "")
    )
    window.location_panel.export_button.click()
    assert ConfigStore(destination).load().locations == (preset,)


def test_corrupt_list_can_restore_backup(qtbot: QtBot, tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "locations.json")
    original = LocationPreset("first", 1, 2)
    store.put_location(original)
    store.put_location(LocationPreset("second", 3, 4))
    store.path.write_text("broken", encoding="utf-8")
    window = GpsWindow(location_store=store)
    qtbot.addWidget(window)
    assert window.location_panel.restore_button.isEnabled()
    window.location_panel.restore_button.click()
    assert store.load().locations == (original,)
    assert window.location_panel.selected_location() == original
    assert "已从最近有效备份恢复" in window.log.toPlainText()
