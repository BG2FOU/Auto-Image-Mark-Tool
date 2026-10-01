"""Minimal Qt bootstrap; workflow UI is added in S7."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


def create_main_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Auto Image Mark Tool")
    window.setCentralWidget(QLabel("Auto Image Mark Tool"))
    window.resize(800, 500)
    return window


def run_gui() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Auto Image Mark Tool")
    window = create_main_window()
    window.show()
    return application.exec()
