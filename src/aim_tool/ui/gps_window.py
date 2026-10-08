"""A local batch GPS page backed by the existing preflight and transaction engine."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import BatchJob, ItemResult, ItemStatus, PhotoItem
from aim_tool.domain.validation import validate_altitude
from aim_tool.services.exiftool import ExifTool, validate_coordinates
from aim_tool.services.storage import ConfigStore
from aim_tool.ui.location_panel import LocationPanel
from aim_tool.ui.workers import BatchWorker
from aim_tool.workflow.engine import ExecutionPlan, build_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep


class GpsWorker(BatchWorker):
    """Preserve the GPS worker API while sharing the batch signal bridge."""


class GpsWindow(QMainWindow):
    """Select photos, assign WGS84 coordinates, preflight, then write copies."""

    def __init__(
        self,
        *,
        allow_nef_after_viewer_check: bool = False,
        location_store: ConfigStore | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Auto Image Mark Tool")
        self.resize(1050, 650)
        self._photos: dict[UUID, PhotoItem] = {}
        self._tool: ExifTool | None = None
        self._worker: GpsWorker | None = None
        self._close_after_run = False
        self.allow_nef_after_viewer_check = allow_nef_after_viewer_check

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(("处理", "照片", "纬度", "经度", "状态", "海拔（米）"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 65)
        self.table.setColumnWidth(1, 440)
        self.table.setColumnWidth(2, 125)
        self.table.setColumnWidth(3, 125)

        self.add_files_button = QPushButton("添加照片")
        self.add_folder_button = QPushButton("添加文件夹")
        self.remove_button = QPushButton("移除所选")
        self.add_files_button.clicked.connect(self._pick_files)
        self.add_folder_button.clicked.connect(self._pick_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        files_row = QHBoxLayout()
        for button in (self.add_files_button, self.add_folder_button, self.remove_button):
            files_row.addWidget(button)
        files_row.addStretch()

        self.bulk_latitude = QLineEdit()
        self.bulk_longitude = QLineEdit()
        self.bulk_altitude = QLineEdit("0")
        self.bulk_latitude.setPlaceholderText("-90 到 90")
        self.bulk_longitude.setPlaceholderText("-180 到 180")
        self.apply_button = QPushButton("应用到勾选照片")
        self.apply_button.clicked.connect(self.apply_bulk_coordinates)
        bulk_row = QHBoxLayout()
        bulk_row.addWidget(QLabel("WGS84 纬度"))
        bulk_row.addWidget(self.bulk_latitude)
        bulk_row.addWidget(QLabel("经度"))
        bulk_row.addWidget(self.bulk_longitude)
        bulk_row.addWidget(QLabel("海拔（米）"))
        bulk_row.addWidget(self.bulk_altitude)
        bulk_row.addWidget(self.apply_button)

        self.location_panel = LocationPanel(location_store, self)
        self.location_panel.apply_position_requested.connect(self.apply_location_coordinates)
        self.location_panel.message.connect(self._message)

        self.output_root_edit = QLineEdit()
        self.output_root_edit.setPlaceholderText("选择与原片目录不同的输出文件夹")
        self.output_button = QPushButton("浏览…")
        self.output_button.clicked.connect(self._pick_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_root_edit)
        output_row.addWidget(self.output_button)
        output_form = QFormLayout()
        output_form.addRow("输出目录", output_row)

        self.preflight_button = QPushButton("检查批次")
        self.run_button = QPushButton("开始写入副本")
        self.cancel_button = QPushButton("取消")
        self.watermark_button = QPushButton("水印工具（后续版本）")
        self.watermark_button.setEnabled(False)
        self.watermark_button.setToolTip("接口已预留；当前版本只写入坐标")
        self.preflight_button.clicked.connect(self.preflight)
        self.run_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        action_row = QHBoxLayout()
        for button in (
            self.preflight_button,
            self.run_button,
            self.cancel_button,
            self.watermark_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch()

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.appendPlainText("坐标系：WGS84。先检查批次，再开始写入；原片保持不变。")
        layout = QVBoxLayout()
        layout.addLayout(files_row)
        layout.addWidget(self.table)
        layout.addLayout(bulk_row)
        layout.addWidget(self.location_panel)
        layout.addLayout(output_form)
        layout.addLayout(action_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.log)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        if self.location_panel.initial_error:
            self._message(self.location_panel.initial_error)

    def _message(self, message: str) -> None:
        self.log.appendPlainText(message)
        self.statusBar().showMessage(message)

    def _pick_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self, "选择照片", "", "照片 (*.jpg *.jpeg *.JPG *.JPEG)"
        )
        if names:
            self.add_photos(tuple(Path(name) for name in names))

    def _pick_folder(self) -> None:
        name = QFileDialog.getExistingDirectory(self, "选择照片文件夹")
        if name:
            root = Path(name)
            paths = tuple(
                path for path in root.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg"}
            )
            self.add_photos(paths, import_root=root)

    def _pick_output(self) -> None:
        name = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if name:
            self.output_root_edit.setText(name)

    def add_photos(self, paths: Sequence[Path], *, import_root: Path | None = None) -> None:
        existing = {photo.source for photo in self._photos.values()}
        added = 0
        self.table.setSortingEnabled(False)
        for path in paths:
            source = path.resolve()
            if source in existing or not source.is_file():
                continue
            if source.suffix.lower() not in {".jpg", ".jpeg", ".nef"}:
                continue
            root = import_root.resolve() if import_root is not None else source.parent
            if not source.is_relative_to(root):
                continue
            photo = PhotoItem(source, root, id=uuid4())
            self._photos[photo.id] = photo
            existing.add(source)
            row = self.table.rowCount()
            self.table.insertRow(row)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked)
            check.setData(Qt.ItemDataRole.UserRole, str(photo.id))
            name = QTableWidgetItem(str(source))
            name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            name.setToolTip(str(source))
            status = QTableWidgetItem("待检查")
            status.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            for column, item in enumerate(
                (check, name, QTableWidgetItem(), QTableWidgetItem(), status, QTableWidgetItem("0"))
            ):
                self.table.setItem(row, column, item)
            added += 1
        self.table.setSortingEnabled(True)
        self._message(f"已添加 {added} 张照片；当前共 {self.table.rowCount()} 张。")

    def remove_selected(self) -> None:
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            check = self.table.item(row, 0)
            if check is not None:
                self._photos.pop(UUID(check.data(Qt.ItemDataRole.UserRole)), None)
            self.table.removeRow(row)

    def _item(self, row: int, column: int) -> QTableWidgetItem:
        item = self.table.item(row, column)
        if item is None:
            raise ValueError(f"第 {row + 1} 行缺少表格单元格")
        return item

    def _checked_rows(self) -> list[tuple[int, PhotoItem]]:
        selected: list[tuple[int, PhotoItem]] = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            if check is not None and check.checkState() == Qt.CheckState.Checked:
                selected.append((row, self._photos[UUID(check.data(Qt.ItemDataRole.UserRole))]))
        return selected

    def apply_bulk_coordinates(self) -> None:
        try:
            latitude = float(self.bulk_latitude.text().strip())
            longitude = float(self.bulk_longitude.text().strip())
            validate_coordinates(latitude, longitude)
            altitude = float(self.bulk_altitude.text().strip() or "0")
            validate_altitude(altitude)
            rows = self._checked_rows()
            if not rows:
                raise ValueError("请先勾选照片")
        except ValueError as error:
            self._message(f"坐标无效：{error}")
            return
        for row, _ in rows:
            self._item(row, 2).setText(str(latitude))
            self._item(row, 3).setText(str(longitude))
            self._item(row, 4).setText("待检查")
            self._item(row, 5).setText(str(altitude))
        self._message(f"已将坐标应用到 {len(rows)} 张勾选照片。")

    def apply_location_coordinates(
        self, latitude: float, longitude: float, altitude: float = 0.0
    ) -> None:
        self.bulk_latitude.setText(str(latitude))
        self.bulk_longitude.setText(str(longitude))
        self.bulk_altitude.setText(str(altitude))
        self.apply_bulk_coordinates()

    def _build_plan(self) -> ExecutionPlan:
        if not self.output_root_edit.text().strip():
            raise ValueError("请选择输出目录")
        selected = self._checked_rows()
        if not selected:
            raise ValueError("请先勾选至少一张照片")
        photos: list[PhotoItem] = []
        for row, original in selected:
            latitude_text = self._item(row, 2).text().strip()
            longitude_text = self._item(row, 3).text().strip()
            try:
                latitude = float(latitude_text)
                longitude = float(longitude_text)
                validate_coordinates(latitude, longitude)
                altitude = float(self._item(row, 5).text().strip() or "0")
                validate_altitude(altitude)
            except ValueError as error:
                raise ValueError(f"第 {row + 1} 行坐标无效：{error}") from error
            photos.append(
                PhotoItem(
                    original.source,
                    original.import_root,
                    id=original.id,
                    metadata=original.metadata,
                    edits=original.edits,
                    taken_on=original.taken_on,
                    coordinates=(latitude, longitude),
                    altitude=altitude,
                )
            )
        if self._tool is None:
            self._tool = ExifTool(persistent=True)
        registry = StepRegistry()
        registry.register(
            LocationStep(self._tool, allow_nef_after_viewer_check=self.allow_nef_after_viewer_check)
        )
        registry.register(ExportStep())
        try:
            return build_plan(
                BatchJob(
                    tuple(photos), preset("location_only"), Path(self.output_root_edit.text())
                ),
                registry,
            )
        finally:
            self._tool.close()

    def preflight(self) -> ExecutionPlan | None:
        try:
            plan = self._build_plan()
        except (OSError, ValueError, RuntimeError) as error:
            self._message(f"检查未通过：{error}")
            return None
        self.progress.setMaximum(len(plan.items))
        self.progress.setValue(0)
        self._message(f"检查通过：{len(plan.items)} 张照片可写入副本；尚未写文件。")
        return plan

    def start(self) -> None:
        if self._worker is not None:
            return
        plan = self.preflight()
        if plan is None:
            return
        self._set_busy(True)
        self._worker = GpsWorker(plan, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_completed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        for control in (
            self.table,
            self.add_files_button,
            self.add_folder_button,
            self.remove_button,
            self.apply_button,
            self.location_panel,
            self.output_root_edit,
            self.output_button,
            self.preflight_button,
            self.run_button,
        ):
            control.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    def _on_progress(self, photo_id: str, message: str) -> None:
        self._message(f"{self._photos[UUID(photo_id)].source.name}: {message}")

    def _on_completed(self, results: tuple[ItemResult, ...]) -> None:
        for result in results:
            for warning in result.warnings:
                self._message(f"警告：{warning}")
            status = result.status.value
            for row in range(self.table.rowCount()):
                check = self.table.item(row, 0)
                if check is not None and check.data(Qt.ItemDataRole.UserRole) == str(
                    result.photo_id
                ):
                    self._item(row, 4).setText(status)
                    break
            if result.status == ItemStatus.SUCCESS:
                self._message(f"成功：{result.output}")
            else:
                self._message(f"{status}：{result.error or result.current_step or ''}")
        self.progress.setValue(len(results))
        successes = sum(result.status == ItemStatus.SUCCESS for result in results)
        self._message(f"批次完成：成功 {successes} / {len(results)}。")

    def _on_worker_finished(self) -> None:
        assert self._worker is not None
        self._worker.deleteLater()
        self._worker = None
        self._set_busy(False)
        if self._close_after_run:
            self.close()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancelled.set()
            self._message("已请求取消；当前文件步骤结束后停止后续照片。")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._close_after_run = True
            self.cancel()
            event.ignore()
            return
        if self._tool is not None:
            self._tool.close()
        super().closeEvent(event)
