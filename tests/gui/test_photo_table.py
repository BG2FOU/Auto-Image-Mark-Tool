"""Stable row edits after view sorting, using the production table model."""

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QSortFilterProxyModel, Qt
from pytestqt.qtbot import QtBot

from aim_tool.ui.photo_table import PhotoSortProxyModel, PhotoTableModel, PhotoTableView


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


def test_altitude_row_edit_and_empty_defaults_zero(tmp_path: Path) -> None:
    source = tmp_path / "a.jpg"
    source.write_bytes(b"stub")
    model = PhotoTableModel()
    model.add_paths((source,))
    index = model.index(0, model.ALTITUDE)
    assert model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(index, "-12.5")
    assert model.snapshot()[0].altitude == -12.5
    assert model.setData(index, "")
    assert model.snapshot()[0].altitude == 0


def test_capture_time_sort_updates_with_metadata_and_keeps_unknown_last(tmp_path: Path) -> None:
    paths = tuple(tmp_path / name for name in ("late.jpg", "early.jpg", "unknown.jpg", "bad.jpg"))
    for path in paths:
        path.write_bytes(b"stub")
    model = PhotoTableModel()
    photos = model.add_paths(paths)
    proxy = PhotoSortProxyModel()
    proxy.setSourceModel(model)
    proxy.sort(model.DATE, Qt.SortOrder.AscendingOrder)
    model.update_metadata(photos[0].id, {"ExifIFD:DateTimeOriginal": "2026:10:13 14:01:02"})
    model.update_metadata(photos[1].id, {"ExifIFD:DateTimeOriginal": "2026:10:13 09:01:02"})
    model.update_metadata(photos[3].id, {"ExifIFD:DateTimeOriginal": "2026:02:30 01:01:01"})

    def names() -> list[str]:
        return [proxy.index(row, model.FILE).data() for row in range(proxy.rowCount())]

    assert names() == ["early.jpg", "late.jpg", "unknown.jpg", "bad.jpg"]
    proxy.sort(model.DATE, Qt.SortOrder.DescendingOrder)
    assert names()[:2] == ["late.jpg", "early.jpg"]
    assert set(names()[2:]) == {"unknown.jpg", "bad.jpg"}
    # A manual watermark date must not replace the actual camera capture time.
    model.setData(model.index(0, model.DATE), "2000-01-01")
    assert names()[:2] == ["late.jpg", "early.jpg"]
    model.update_metadata(photos[1].id, {"ExifIFD:DateTimeOriginal": "2026:10:14 09:01:02"})
    assert names()[:2] == ["early.jpg", "late.jpg"]


def test_capture_subseconds_and_explicit_fallback_policy(tmp_path: Path) -> None:
    paths = tuple(tmp_path / f"{number}.jpg" for number in range(3))
    for path in paths:
        path.write_bytes(b"stub")
    model = PhotoTableModel()
    photos = model.add_paths(paths)
    for number, subsecond in enumerate(("900", "010")):
        model.update_metadata(
            photos[number].id,
            {
                "ExifIFD:DateTimeOriginal": "2026:10:13 09:01:02",
                "ExifIFD:SubSecTimeOriginal": subsecond,
            },
        )
    model.update_metadata(photos[2].id, {"ExifIFD:CreateDate": "2026:10:12 23:59:59"})
    proxy = PhotoSortProxyModel()
    proxy.setSourceModel(model)
    proxy.sort(model.DATE, Qt.SortOrder.AscendingOrder)
    assert [proxy.index(i, model.FILE).data() for i in range(3)] == ["1.jpg", "0.jpg", "2.jpg"]
    assert model.capture_time(2) is None
    model.allow_create_date = True
    model._changed(2)
    assert proxy.index(0, model.FILE).data() == "2.jpg"
    model.allow_create_date = False
    model.setData(model.index(2, model.DATE), "2026-10-11")
    assert proxy.index(0, model.FILE).data() == "2.jpg"
