"""Workflow text stays readable when window, splitter and log compete for space."""

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton
from pytestqt.qtbot import QtBot

from aim_tool.services.storage import ConfigStore, WatermarkSettingsStore
from aim_tool.ui.main_window import MainWindow


def _assert_readable(window: MainWindow) -> None:
    panel = window.workflow
    for label in panel.content.findChildren(QLabel):
        required = label.heightForWidth(label.width())
        assert label.height() >= max(required, label.fontMetrics().height()), label.text()
        assert label.font().pixelSize() >= 11
    for control in panel.content.findChildren(QCheckBox):
        assert control.height() >= control.minimumSizeHint().height()
        assert control.width() >= control.minimumSizeHint().width()
        assert control.font().pixelSize() >= 12
    button = panel.content.findChild(QPushButton)
    assert button is not None
    assert button.size().width() >= button.minimumSizeHint().width()
    assert button.size().height() >= button.minimumSizeHint().height()


@pytest.mark.parametrize("with_log", [False, True])
def test_workflow_resizes_scrolls_and_restores_text(
    qtbot: QtBot, tmp_path: Path, with_log: bool
) -> None:
    window = MainWindow(
        settings_store=WatermarkSettingsStore(tmp_path / "settings.json"),
        location_store=ConfigStore(tmp_path / "locations.json"),
        workflow_store=ConfigStore(tmp_path / "workflows.json"),
    )
    qtbot.addWidget(window)
    window.resize(1440, 1000)
    window.show()
    panel = window.workflow
    qtbot.waitUntil(lambda: panel.location.font().pixelSize() == 13)
    _assert_readable(window)
    panel.presets.setCurrentIndex(2)
    for _ in range(3):
        window.resize(1100, 720)
        window.log.setVisible(with_log)
        window.splitter.setSizes([190, 600, 400])
        qtbot.waitUntil(lambda: panel.location.font().pixelSize() == 12)
        qtbot.waitUntil(lambda: panel.scroll_area.verticalScrollBar().maximum() > 0)
        _assert_readable(window)
        assert panel.location.isChecked() and panel.watermark.isChecked()
        # The bottom note and both step controls remain reachable in a short viewport.
        for widget in [*panel.content.findChildren(QLabel), panel.location, panel.watermark]:
            panel.scroll_area.ensureWidgetVisible(widget)
            position = widget.mapTo(panel.scroll_area.viewport(), QPoint())
            assert position.y() >= 0
            assert position.y() + widget.height() <= panel.scroll_area.viewport().height()
        window.log.hide()
        window.resize(1440, 1000)
        window.splitter.setSizes([210, 760, 420])
        qtbot.waitUntil(lambda: panel.location.font().pixelSize() == 13)
        qtbot.waitUntil(lambda: panel.scroll_area.verticalScrollBar().maximum() == 0)
        _assert_readable(window)
    window.close()
