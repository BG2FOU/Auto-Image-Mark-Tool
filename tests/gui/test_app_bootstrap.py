"""S1 Qt window smoke test."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow
from pytestqt.qtbot import QtBot

from aim_tool.app import create_main_window, show_main_window


def test_empty_window_starts(qtbot: QtBot) -> None:
    window = create_main_window()
    qtbot.addWidget(window)
    window.show()
    assert isinstance(window, QMainWindow)
    assert window.isVisible()
    assert window.windowTitle() == "Auto Image Mark Tool"


def test_main_launch_starts_maximized_without_entering_borderless_fullscreen(qtbot: QtBot) -> None:
    window = create_main_window()
    qtbot.addWidget(window)
    show_main_window(window)
    assert window.isVisible() and window.isMaximized()
    assert not window.isFullScreen()
    window.close()


def test_standalone_gps_keeps_its_existing_initial_window_state(qtbot: QtBot) -> None:
    window = create_main_window(gps_only=True)
    qtbot.addWidget(window)
    show_main_window(window, gps_only=True)
    assert window.isVisible() and not window.isMaximized()
    window.close()


def test_jpg_selftest_resolves_temp_directory_alias(tmp_path: Path) -> None:
    import json
    import os
    import subprocess
    import sys

    import pytest

    target = tmp_path / "real"
    target.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory aliases requires unavailable platform permissions")
    environment = os.environ.copy()
    environment.update(
        TMPDIR=str(alias), TEMP=str(alias), TMP=str(alias), QT_QPA_PLATFORM="offscreen"
    )
    report = tmp_path / "selftest.json"
    completed = subprocess.run(
        [sys.executable, "-m", "aim_tool", "--self-test-jpg", "--report", str(report)],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    result = json.loads(report.read_text(encoding="utf-8"))
    assert completed.returncode == 0, (result, completed.stderr)
    assert result["ok"] is True
