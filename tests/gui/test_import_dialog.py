"""Applying edits requires an error-free, explicitly confirmed matching preview."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from aim_tool.domain import PhotoItem
from aim_tool.ui.import_dialog import ImportDialog


def test_header_mapping_preview_and_invalidation(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "a.jpg"
    source.write_bytes(b"stub")
    dialog = ImportDialog((PhotoItem(source, tmp_path),))
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(1)
    dialog.pasted.setPlainText("照片名\t编号\t类别\na.jpg\tB-1356\taviation\n")
    dialog.mapping.setPlainText("照片名=file_name\n编号=subject")
    assert not dialog.apply_button.isEnabled()
    dialog.generate_preview()
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert dialog.preview is not None and not dialog.preview.errors
    assert dialog.apply_button.isEnabled()
    assert dialog.table.item(0, 2).text() == "B-1356"
    dialog.pasted.setPlainText("文件名\nunknown.jpg\n")
    assert not dialog.apply_button.isEnabled()
    assert dialog.preview is None


def test_ambiguous_matches_disable_application(qtbot: QtBot, tmp_path: Path) -> None:
    first, second = tmp_path / "one/same.jpg", tmp_path / "two/same.jpg"
    for path in (first, second):
        path.parent.mkdir()
        path.write_bytes(b"stub")
    dialog = ImportDialog(tuple(PhotoItem(path, path.parent) for path in (first, second)))
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(1)
    dialog.pasted.setPlainText("file_name\nsame.jpg\n")
    dialog.generate_preview()
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert not dialog.apply_button.isEnabled()
    assert "ambiguous" in dialog.summary.text()
