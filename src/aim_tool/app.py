"""Qt bootstrap for JPG workflows and the standalone GPS preview."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from aim_tool.ui.gps_window import GpsWindow


def create_main_window(*, gps_only: bool = False) -> QMainWindow:
    if gps_only:
        return GpsWindow()
    from aim_tool.ui.main_window import MainWindow

    return MainWindow()


def run_gui(*, gps_only: bool = False) -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Auto Image Mark Tool")
    application.setStyle("Fusion")
    window = create_main_window(gps_only=gps_only)
    window.show()
    return application.exec()
