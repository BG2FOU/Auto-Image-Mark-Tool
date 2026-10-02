"""Stable row edits after view sorting, using the production table model."""

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QSortFilterProxyModel, Qt
from pytestqt.qtbot import QtBot

from aim_tool.ui.photo_table import PhotoTableModel, PhotoTableView


def test_sorted_edits_and_checked_selection_use_photo_ids(qtbot: QtBot, tmp_path: Path) -> None:
    first, second = tmp_path / "z.jpg", tmp_path / "a.JPEG"
    first.write_bytes(b"stub")
    second.write_bytes(b"stub")
    model = PhotoTableModel()
    added = model.add_paths((first, second))
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(model)
    view = PhotoTableView()
    qtbot.addWidget(view)
    view.setModel(proxy)
    view.sortByColumn(model.FILE, Qt.SortOrder.AscendingOrder)
    target = UUID(proxy.index(0, model.FILE).data(Qt.ItemDataRole.UserRole))
    assert target == added[1].id
    proxy.setData(proxy.index(0, model.SUBJECT), "B-1356")
    proxy.setData(
        proxy.index(1, model.CHECK), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
    )
    photos = model.snapshot()
    assert len(photos) == 1 and photos[0].id == target
    assert photos[0].edits["subject"] == "B-1356"
    assert "subject" not in model.rows[0].photo.edits


def test_manual_date_and_coordinate_errors_are_preflighted(tmp_path: Path) -> None:
    source = tmp_path / "one.jpg"
    source.write_bytes(b"stub")
    model = PhotoTableModel()
    model.add_paths((source,))
    model.setData(model.index(0, model.DATE), "2026-09-26T23:10:01+08:00")
    model.setData(model.index(0, model.LATITUDE), "-24.5")
    model.setData(model.index(0, model.LONGITUDE), "118.5")
    photo = model.snapshot()[0]
    assert str(photo.taken_on) == "2026-09-26"
    assert photo.edits["capture_date_source"] == "manual"
    assert photo.coordinates == (-24.5, 118.5)
    model.setData(model.index(0, model.DATE), "")
    assert model.snapshot()[0].taken_on is None
