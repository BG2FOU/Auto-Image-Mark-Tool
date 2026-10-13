"""Digital controls share defaults and preserve local keys and layout settings."""

import json
from pathlib import Path

from pytestqt.qtbot import QtBot

from aim_tool.services.storage import ConfigStore, WatermarkSettings, WatermarkSettingsStore
from aim_tool.services.watermark import WatermarkResources
from aim_tool.ui.main_window import MainWindow
from aim_tool.ui.settings_dialog import SettingsDialog


def test_workflow_controls_migrate_roundtrip_and_preserve_unrelated_defaults(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    store = WatermarkSettingsStore(tmp_path / "settings.json")
    original = WatermarkSettings(synthetic_watermark_resources, {"font_size_pt": 24})
    store.save(original)
    window = MainWindow(
        settings_store=store,
        location_store=ConfigStore(tmp_path / "locations.json"),
        workflow_store=ConfigStore(tmp_path / "workflows.json"),
    )
    qtbot.addWidget(window)
    controls = window.workflow.digital
    assert controls.enabled.isChecked()
    assert controls.algorithm.currentData() == "dct"
    assert controls.level.currentData() == "medium"
    assert not controls.isEnabled()  # Coordinates-only remains the initial workflow.
    key = store.load().params["digital_key"]
    assert len(str(key)) == 64
    backup = json.loads(store.backup.read_text())
    assert backup["params"] == {"font_size_pt": 24}
    window.workflow.presets.setCurrentIndex(1)
    assert controls.isEnabled()
    temporary = dict(window.settings.params)
    temporary["font_size_pt"] = 40  # A temporary layout change must not become a default.
    window.settings = WatermarkSettings(window.settings.resources, temporary)
    controls.algorithm.setCurrentIndex(1)
    controls.level.setCurrentIndex(2)
    saved = store.load()
    assert saved.params["digital_algorithm"] == "fft"
    assert saved.params["digital_level"] == "high"
    assert saved.params["font_size_pt"] == 24
    assert saved.params["digital_key"] == key
    window._save_workflow("FFT high")
    controls.algorithm.setCurrentIndex(0)
    controls.level.setCurrentIndex(0)
    window.workflow.presets.setCurrentIndex(window.workflow.presets.findData("saved:FFT high"))
    assert controls.algorithm.currentData() == "fft"
    assert controls.level.currentData() == "high"
    assert window.settings.params["digital_key"] == key
    controls.enabled.setChecked(False)
    assert not controls.algorithm.isEnabled() and not controls.level.isEnabled()
    assert store.load().params["digital_enabled"] is False
    window.close()


def test_settings_dialog_keeps_key_on_project_defaults_and_reopens_choice(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    store = WatermarkSettingsStore(tmp_path / "settings.json")
    dialog = SettingsDialog(WatermarkSettings(synthetic_watermark_resources), store)
    qtbot.addWidget(dialog)
    key = dialog.settings().params["digital_key"]
    dialog.digital.algorithm.setCurrentIndex(1)
    dialog.digital.level.setCurrentIndex(0)
    dialog.save_defaults()
    saved = store.load()
    assert saved.params["digital_algorithm"] == "fft"
    assert saved.params["digital_level"] == "low"
    assert saved.params["digital_key"] == key
    dialog._populate(WatermarkSettings(synthetic_watermark_resources))
    assert dialog.digital.algorithm.currentData() == "dct"
    assert dialog.digital.level.currentData() == "medium"
    assert dialog.settings().params["digital_key"] == key


def test_failed_key_persistence_keeps_enabled_state_and_stops_export(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    from PIL import Image

    store = WatermarkSettingsStore(tmp_path / "settings.json")
    store.path.write_text("broken config")
    window = MainWindow(
        settings_store=store,
        location_store=ConfigStore(tmp_path / "locations.json"),
        workflow_store=ConfigStore(tmp_path / "workflows.json"),
    )
    qtbot.addWidget(window)
    assert window.settings.params["digital_enabled"] is True
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (600, 400)).save(source)
    window.add_photos((source,))
    window.workflow.presets.setCurrentIndex(1)
    window.bulk_subject.setText("B-1356")
    window.bulk_date.setText("2026/10/13")
    window.apply_fields_button.click()
    window.output_edit.setText(str(tmp_path / "out"))
    window.preflight(execute=True)
    assert "Cannot read watermark settings" in window.status.text()
    assert store.path.read_text() == "broken config"
    assert not (tmp_path / "out").exists()
    window.close()
    qtbot.waitUntil(lambda: not window.has_active_workers, timeout=20000)
