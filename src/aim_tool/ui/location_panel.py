"""WGS84 location presets for the GPS page."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from platformdirs import user_config_path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import LocationPreset
from aim_tool.services.exiftool import validate_coordinates
from aim_tool.services.storage import AppConfig, ConfigError, ConfigStore


def default_location_store() -> ConfigStore:
    """Keep portable Windows EXE presets beside the executable."""
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        return ConfigStore(Path(sys.executable).resolve().parent / "locations.json")
    return ConfigStore(user_config_path("AutoImageMarkTool", "BG2FOU") / "locations.json")


class LocationDialog(QDialog):
    def __init__(self, parent: QWidget, existing: LocationPreset | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑坐标" if existing else "新增坐标")
        self.name_edit = QLineEdit(existing.name if existing else "")
        self.latitude_edit = QLineEdit(str(existing.latitude) if existing else "")
        self.longitude_edit = QLineEdit(str(existing.longitude) if existing else "")
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #b00020")
        self._original_id = existing.id if existing else None
        form = QFormLayout()
        form.addRow("名称", self.name_edit)
        form.addRow("WGS84 纬度", self.latitude_edit)
        form.addRow("WGS84 经度", self.longitude_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def preset(self) -> LocationPreset:
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("请输入坐标名称")
        latitude = float(self.latitude_edit.text().strip())
        longitude = float(self.longitude_edit.text().strip())
        validate_coordinates(latitude, longitude)
        if self._original_id is None:
            return LocationPreset(name, latitude, longitude)
        return LocationPreset(name, latitude, longitude, id=self._original_id)

    def _validate_and_accept(self) -> None:
        try:
            self.preset()
        except ValueError as error:
            self.error_label.setText(f"坐标无效：{error}")
            return
        self.accept()


class LocationPanel(QWidget):
    apply_requested = Signal(float, float)
    message = Signal(str)

    def __init__(self, store: ConfigStore | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store or default_location_store()
        self._locations: tuple[LocationPreset, ...] = ()
        self.initial_error: str | None = None
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索坐标名称")
        self.location_combo = QComboBox()
        self.location_combo.setMinimumWidth(280)
        self.path_label = QLabel(f"坐标列表：{self.store.path}")
        self.path_label.setToolTip(str(self.store.path))
        self.restore_button = QPushButton("从备份恢复")
        self.new_button = QPushButton("新增")
        self.edit_button = QPushButton("编辑")
        self.delete_button = QPushButton("删除")
        self.import_button = QPushButton("导入")
        self.export_button = QPushButton("导出")
        self.apply_button = QPushButton("应用到勾选照片")
        row = QHBoxLayout()
        row.addWidget(QLabel("WGS84 坐标列表"))
        row.addWidget(self.search_edit)
        row.addWidget(self.location_combo)
        for button in (
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.import_button,
            self.export_button,
            self.apply_button,
        ):
            row.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(row)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_label)
        path_row.addWidget(self.restore_button)
        layout.addLayout(path_row)
        self.search_edit.textChanged.connect(self._refresh)
        self.new_button.clicked.connect(self.add_location)
        self.edit_button.clicked.connect(self.edit_location)
        self.delete_button.clicked.connect(self.delete_location)
        self.import_button.clicked.connect(self.import_locations)
        self.export_button.clicked.connect(self.export_locations)
        self.restore_button.clicked.connect(self.restore_backup)
        self.apply_button.clicked.connect(self.apply_location)
        try:
            self._locations = self.store.load().locations
        except ConfigError as error:
            self.initial_error = f"坐标列表无法读取：{error}；原文件未改动。"
        self._refresh()

    def _refresh(self) -> None:
        selected = self.location_combo.currentData()
        query = self.search_edit.text().strip().casefold()
        self.location_combo.clear()
        for location in self._locations:
            if query and query not in location.name.casefold():
                continue
            self.location_combo.addItem(
                f"{location.name} ({location.latitude}, {location.longitude})", str(location.id)
            )
        if selected is not None:
            index = self.location_combo.findData(selected)
            if index >= 0:
                self.location_combo.setCurrentIndex(index)
        has_selection = self.location_combo.currentIndex() >= 0
        for button in (self.edit_button, self.delete_button, self.apply_button):
            button.setEnabled(has_selection)
        self.export_button.setEnabled(bool(self._locations))
        self.restore_button.setEnabled(self.store.backup.is_file())

    def selected_location(self) -> LocationPreset | None:
        selected = self.location_combo.currentData()
        return next((item for item in self._locations if str(item.id) == selected), None)

    def _reload(self, selected_id: UUID | None = None) -> None:
        self._locations = self.store.load().locations
        self._refresh()
        if selected_id is not None:
            index = self.location_combo.findData(str(selected_id))
            if index >= 0:
                self.location_combo.setCurrentIndex(index)

    def save_location(self, location: LocationPreset) -> None:
        try:
            self.store.put_location(location)
            self._reload(location.id)
        except (ConfigError, OSError) as error:
            self.message.emit(f"保存坐标失败：{error}")
            return
        self.message.emit(f"已保存坐标：{location.name}")

    def add_location(self) -> None:
        dialog = LocationDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_location(dialog.preset())

    def edit_location(self) -> None:
        location = self.selected_location()
        if location is None:
            return
        dialog = LocationDialog(self, location)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_location(dialog.preset())

    def delete_location(self) -> None:
        location = self.selected_location()
        if location is None:
            return
        try:
            self.store.delete_location(location.id)
            self._reload()
        except (ConfigError, OSError) as error:
            self.message.emit(f"删除坐标失败：{error}")
            return
        self.message.emit(f"已删除坐标：{location.name}")

    def restore_backup(self) -> None:
        try:
            self.store.restore_backup()
            self._reload()
        except (ConfigError, OSError) as error:
            self.message.emit(f"恢复坐标列表失败：{error}")
            return
        self.message.emit("已从最近有效备份恢复坐标列表。")

    def apply_location(self) -> None:
        location = self.selected_location()
        if location is not None:
            self.apply_requested.emit(location.latitude, location.longitude)

    def import_locations(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "导入坐标列表", "", "JSON (*.json)")
        if not filename:
            return
        try:
            if not Path(filename).is_file():
                raise ConfigError(f"坐标列表不存在：{filename}")
            imported = ConfigStore(Path(filename)).load().locations
            current = self.store.load()
            by_id = {item.id: item for item in current.locations}
            by_id.update({item.id: item for item in imported})
            self.store.save(AppConfig(current.workflows, tuple(by_id.values())))
            self._reload()
        except (ConfigError, OSError) as error:
            self.message.emit(f"导入坐标失败：{error}")
            return
        self.message.emit(f"已导入 {len(imported)} 个坐标；同 ID 坐标已更新。")

    def export_locations(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出坐标列表", "locations.json", "JSON (*.json)"
        )
        if not filename:
            return
        try:
            target = Path(filename)
            if target.resolve() == self.store.path.resolve():
                raise ValueError("导出路径不能是当前坐标列表")
            ConfigStore(target).save(AppConfig(locations=self._locations))
        except (ConfigError, OSError, ValueError) as error:
            self.message.emit(f"导出坐标失败：{error}")
            return
        self.message.emit(f"已导出 {len(self._locations)} 个坐标到 {filename}")
