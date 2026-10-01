"""S1 Qt window smoke test."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow
from pytestqt.qtbot import QtBot

from aim_tool.app import create_main_window


def test_empty_window_starts(qtbot: QtBot) -> None:
    window = create_main_window()
    qtbot.addWidget(window)
    window.show()
    assert isinstance(window, QMainWindow)
    assert window.isVisible()
    assert window.windowTitle() == "Auto Image Mark Tool"
