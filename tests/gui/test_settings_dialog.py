"""Settings can be replaced, saved, reopened and restored without copying assets."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from aim_tool.services.storage import WatermarkSettings, WatermarkSettingsStore
from aim_tool.services.watermark import WatermarkResources
from aim_tool.ui.settings_dialog import SettingsDialog


def test_local_settings_and_asset_preview_roundtrip(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    store = WatermarkSettingsStore(tmp_path / "settings.json")
    dialog = SettingsDialog(WatermarkSettings(synthetic_watermark_resources), store)
    qtbot.addWidget(dialog)
    assert dialog.check_assets()
    assert dialog.signature_preview.pixmap() is not None
    dialog.numbers["font_size_pt"].setValue(24)
    dialog.numbers["signature_width"].setValue(220)
    dialog.anchor.setCurrentIndex(3)
    dialog.numbers["latin_opacity"].setValue(30)
    dialog.save_defaults()
    reopened = store.load()
    assert reopened.params["font_size_pt"] == 24
    assert reopened.params["signature_width"] == 220
    assert reopened.params["anchor"] == "top_left"
    assert reopened.params["latin_opacity"] == 0.3
    assert reopened.resources == synthetic_watermark_resources
    assert not list(tmp_path.glob(".aim-settings-*"))
