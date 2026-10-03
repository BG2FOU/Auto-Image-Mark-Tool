"""Editable photo rows with stable IDs under sorting and filtering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import UUID

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from aim_tool.domain import ItemResult, ItemStatus, PhotoItem
from aim_tool.domain.dates import resolve_capture_date
from aim_tool.domain.validation import validate_altitude, validate_coordinates
from aim_tool.services.table_import import apply_manual_date

EMPTY_INDEX = QModelIndex()

CATEGORIES = {"aviation": "航空", "railway": "铁路", "landscape": "风光"}
STATUS = {ItemStatus.SUCCESS: "已完成", ItemStatus.FAILED: "失败", ItemStatus.CANCELLED: "已取消"}


@dataclass
class PhotoRow:
    photo: PhotoItem
    checked: bool = True
    status: str = "待处理"
    error: str = ""
    output: str = ""


class PhotoTableModel(QAbstractTableModel):
    message = Signal(str)
    edited = Signal()
    (
        CHECK,
        FILE,
        CATEGORY,
        SUBJECT,
        DATE,
        DATE_SOURCE,
        LATITUDE,
        LONGITUDE,
        STATUS,
        OUTPUT,
        ALTITUDE,
    ) = range(11)
    HEADERS = (
        "处理",
        "照片",
        "类别",
        "内容 / 编号",
        "拍摄日期",
        "日期来源",
        "纬度",
        "经度",
        "状态",
        "输出",
        "海拔（米）",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[PhotoRow] = []
        self.allow_create_date = False

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = EMPTY_INDEX) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = EMPTY_INDEX) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return self.HEADERS[section] if orientation == Qt.Orientation.Horizontal else section + 1

    def _date(self, photo: PhotoItem) -> tuple[str, str]:
        if "date_input" in photo.edits:
            return photo.edits["date_input"], "手动"
        try:
            resolved = resolve_capture_date(
                manual=photo.taken_on,
                exif_datetime_original=photo.metadata.get("ExifIFD:DateTimeOriginal"),
                exif_create_date=photo.metadata.get("ExifIFD:CreateDate"),
                allow_create_date=self.allow_create_date,
            )
            source = photo.edits.get("capture_date_source", resolved.source)
            return resolved.day.isoformat(), {
                "manual": "手动",
                "table": "表格",
                "EXIF CreateDate": "CreateDate",
            }.get(source, "EXIF")
        except ValueError:
            return "", "待读取" if not photo.metadata else "缺失 / 无效"

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = 0) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        row = self.rows[index.row()]
        photo = row.photo
        column = index.column()
        if role == Qt.ItemDataRole.UserRole:
            return str(photo.id)
        if role == Qt.ItemDataRole.CheckStateRole and column == self.CHECK:
            return Qt.CheckState.Checked if row.checked else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == self.FILE:
                return str(photo.source)
            if column == self.STATUS:
                return row.error or row.status
            if column == self.DATE:
                return photo.edits.get(
                    "capture_date_original", photo.metadata.get("ExifIFD:DateTimeOriginal", "")
                )
        if role == Qt.ItemDataRole.ForegroundRole and column == self.STATUS:
            return QBrush(
                QColor(
                    "#15803d" if row.status == "已完成" else "#b91c1c" if row.error else "#64748b"
                )
            )
        if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole}:
            day, source = self._date(photo)
            coordinates = photo.coordinates
            values = (
                "",
                photo.source.name,
                photo.edits.get("category", ""),
                photo.edits.get("subject", ""),
                day,
                source,
                photo.edits.get("latitude_input", str(coordinates[0]) if coordinates else ""),
                photo.edits.get("longitude_input", str(coordinates[1]) if coordinates else ""),
                row.status,
                row.output,
                photo.edits.get("altitude_input", str(photo.altitude)),
            )
            value = values[column]
            return (
                CATEGORIES.get(value, "未设置")
                if column == self.CATEGORY and role == Qt.ItemDataRole.DisplayRole
                else value
            )
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.CHECK:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() in {
            self.CATEGORY,
            self.SUBJECT,
            self.DATE,
            self.LATITUDE,
            self.LONGITUDE,
            self.ALTITUDE,
        }:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = int(Qt.ItemDataRole.EditRole),
    ) -> bool:
        if not index.isValid():
            return False
        row = self.rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.CheckStateRole and column == self.CHECK:
            row.checked = value == Qt.CheckState.Checked or value == Qt.CheckState.Checked.value
        elif role == Qt.ItemDataRole.EditRole and column in {
            self.CATEGORY,
            self.SUBJECT,
            self.DATE,
            self.LATITUDE,
            self.LONGITUDE,
            self.ALTITUDE,
        }:
            edits = dict(row.photo.edits)
            key = {
                self.CATEGORY: "category",
                self.SUBJECT: "subject",
                self.DATE: "date_input",
                self.LATITUDE: "latitude_input",
                self.LONGITUDE: "longitude_input",
                self.ALTITUDE: "altitude_input",
            }[column]
            text = str(value).strip()
            if column == self.CATEGORY and text not in CATEGORIES and text:
                return False
            edits[key] = text
            if column == self.DATE and not text:
                edits.pop("date_input", None)
                edits.pop("capture_date_source", None)
                edits.pop("capture_date_original", None)
                row.photo = replace(row.photo, taken_on=None)
            row.photo = replace(row.photo, edits=edits)
            row.status, row.error, row.output = "待处理", "", ""
        else:
            return False
        self._changed(index.row())
        self.edited.emit()
        return True

    def _changed(self, row: int) -> None:
        self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1), [])

    def add_paths(
        self, paths: Sequence[Path], import_root: Path | None = None
    ) -> tuple[PhotoItem, ...]:
        existing = {row.photo.source for row in self.rows}
        added = []
        for path in paths:
            source = path.resolve()
            if (
                source in existing
                or not source.is_file()
                or source.suffix.lower() not in {".jpg", ".jpeg", ".nef"}
            ):
                continue
            root = import_root.resolve() if import_root is not None else source.parent
            if not source.is_relative_to(root):
                continue
            photo = PhotoItem(source, root)
            added.append(photo)
            existing.add(source)
        if added:
            first = len(self.rows)
            self.beginInsertRows(QModelIndex(), first, first + len(added) - 1)
            self.rows.extend(PhotoRow(photo) for photo in added)
            self.endInsertRows()
        return tuple(added)

    def remove_ids(self, ids: set[UUID]) -> None:
        for number in range(len(self.rows) - 1, -1, -1):
            if self.rows[number].photo.id in ids:
                self.beginRemoveRows(QModelIndex(), number, number)
                del self.rows[number]
                self.endRemoveRows()

    def snapshot(
        self, *, checked_only: bool = True, ids: set[UUID] | None = None
    ) -> tuple[PhotoItem, ...]:
        photos = []
        for row in self.rows:
            photo = row.photo
            if checked_only and not row.checked or ids is not None and photo.id not in ids:
                continue
            if "date_input" in photo.edits:
                photo = apply_manual_date(photo, photo.edits["date_input"])
            latitude = photo.edits.get(
                "latitude_input", str(photo.coordinates[0]) if photo.coordinates else ""
            )
            longitude = photo.edits.get(
                "longitude_input", str(photo.coordinates[1]) if photo.coordinates else ""
            )
            if bool(latitude) != bool(longitude):
                raise ValueError(f"{photo.source.name}：纬度和经度必须同时填写")
            if latitude:
                coordinates = (float(latitude), float(longitude))
                validate_coordinates(*coordinates)
                photo = replace(photo, coordinates=coordinates)
            else:
                photo = replace(photo, coordinates=None)
            altitude = photo.edits.get("altitude_input", str(photo.altitude))
            altitude_value = float(altitude.strip() or "0")
            validate_altitude(altitude_value)
            photo = replace(photo, altitude=altitude_value)
            photos.append(photo)
        return tuple(photos)

    def update_photos(self, photos: Sequence[PhotoItem]) -> None:
        updates = {photo.id: photo for photo in photos}
        for number, row in enumerate(self.rows):
            if row.photo.id in updates:
                row.photo = updates[row.photo.id]
                row.status, row.error, row.output = "待处理", "", ""
                self._changed(number)
        self.edited.emit()

    def update_metadata(self, photo_id: UUID, metadata: dict[str, str]) -> None:
        for number, row in enumerate(self.rows):
            if row.photo.id == photo_id:
                row.photo = replace(row.photo, metadata=metadata)
                self._changed(number)
                return

    def mark_results(self, results: tuple[ItemResult, ...]) -> None:
        by_id = {result.photo_id: result for result in results}
        for number, row in enumerate(self.rows):
            result = by_id.get(row.photo.id)
            if result is not None:
                row.status = STATUS[result.status]
                row.error = result.error or ""
                row.output = str(result.output) if result.output else ""
                self._changed(number)

    def preflight_error(self, photo_id: str, error: str) -> None:
        for number, row in enumerate(self.rows):
            if str(row.photo.id) == photo_id:
                row.status, row.error = "检查失败", error
                self._changed(number)
                return

    def retry_failed(self) -> None:
        for number, row in enumerate(self.rows):
            row.checked = row.status in {"失败", "已取消"}
            if row.checked:
                row.status, row.error = "待处理", ""
            self._changed(number)
        self.edited.emit()


class CategoryDelegate(QStyledItemDelegate):
    def createEditor(
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QWidget:
        combo = QComboBox(parent)
        combo.addItem("未设置", "")
        for key, label in CATEGORIES.items():
            combo.addItem(label, key)
        return combo

    def setEditorData(self, editor: QWidget, index: QModelIndex | QPersistentModelIndex) -> None:
        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(0, editor.findData(index.data(Qt.ItemDataRole.EditRole))))

    def setModelData(
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)


class PhotoTableView(QTableView):
    files_dropped = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setItemDelegateForColumn(PhotoTableModel.CATEGORY, CategoryDelegate(self))
        self.verticalHeader().setDefaultSectionSize(38)
        self.verticalHeader().hide()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = tuple(
            Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()
        )
        self.files_dropped.emit(paths)
        event.acceptProposedAction()
