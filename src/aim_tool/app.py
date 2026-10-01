"""Qt bootstrap for the local GPS workflow."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from aim_tool.ui.gps_window import GpsWindow


def create_main_window() -> QMainWindow:
    return GpsWindow()


def run_gui() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Auto Image Mark Tool")
    window = create_main_window()
    window.show()
    return application.exec()
