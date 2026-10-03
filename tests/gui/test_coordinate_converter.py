"""Conversion preview invalidation, safe list append and reverse-direction guard."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from aim_tool.domain import LocationPreset
from aim_tool.services.storage import ConfigStore
from aim_tool.ui.coordinate_converter import CoordinateConverterDialog


def test_convert_preview_save_altitude_and_original_location(qtbot: QtBot, tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "locations.json")
    original = LocationPreset("original", 0, 0)
    store.put_location(original)
    dialog = CoordinateConverterDialog(store)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.input.setPlainText(
        "name,latitude,longitude,altitude\nTest,39.91334545536069,116.38404722455657,-12.5"
    )
    dialog.convert()
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert dialog.save_button.isEnabled()
    assert "WGS84" in dialog.output.toPlainText()
    assert not store.backup.exists()
    dialog.save_locations()
    locations = store.load().locations
    assert locations[0] == original and len(locations) == 2
    assert abs(locations[1].latitude - 39.911954) < 2e-7
    assert locations[1].altitude == -12.5
    dialog.save_locations()
    assert store.load().locations == locations
    dialog.input.setPlainText("bad,91,2")
    assert not dialog.save_button.isEnabled()
    dialog.convert()
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert not dialog.rows and not dialog.save_button.isEnabled()
    assert store.load().locations == locations


def test_reverse_result_cannot_be_saved_as_wgs84(qtbot: QtBot, tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "locations.json")
    dialog = CoordinateConverterDialog(store)
    qtbot.addWidget(dialog)
    dialog.direction.setCurrentIndex(1)
    dialog.input.setPlainText("39.911954,116.377817")
    dialog.convert()
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert dialog.rows and "GCJ-02" in dialog.output.toPlainText()
    assert not dialog.save_button.isEnabled()
    dialog.save_locations()
    assert not store.path.exists()
    dialog.direction.setCurrentIndex(0)
    assert not dialog.rows and not dialog.copy_button.isEnabled()


def test_escape_waits_for_conversion_worker(qtbot: QtBot, tmp_path: Path, monkeypatch) -> None:
    from threading import Event

    from aim_tool.ui import coordinate_converter

    started, release = Event(), Event()
    original = coordinate_converter.convert_row

    def slow_convert(row, direction):
        started.set()
        assert release.wait(10)
        return original(row, direction)

    monkeypatch.setattr(coordinate_converter, "convert_row", slow_convert)
    store = ConfigStore(tmp_path / "locations.json")
    dialog = CoordinateConverterDialog(store)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.input.setPlainText("39.9,116.3")
    dialog.convert()
    try:
        qtbot.waitUntil(started.is_set, timeout=10000)
        dialog.reject()
        assert dialog.isVisible() and dialog._worker is not None
        assert dialog._worker.isInterruptionRequested()
    finally:
        release.set()
        qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
        qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=10000)
    assert not store.path.exists()
