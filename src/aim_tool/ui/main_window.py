"""Photo batch workspace: ordered workflows, stable rows and live watermark preview."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import BatchJob, ItemResult, ItemStatus, PhotoItem
from aim_tool.domain.dates import parse_capture_date
from aim_tool.domain.models import Parameter
from aim_tool.domain.validation import validate_coordinates
from aim_tool.services.resources import default_local_resources
from aim_tool.services.storage import ConfigStore, WatermarkSettings, WatermarkSettingsStore
from aim_tool.services.table_import import apply_import, apply_manual_date
from aim_tool.services.templates import project_default_config
from aim_tool.services.watermark import watermark_scale
from aim_tool.ui.about_dialog import AboutDialog
from aim_tool.ui.import_dialog import ImportDialog
from aim_tool.ui.location_panel import LocationPanel
from aim_tool.ui.photo_table import CATEGORIES, PhotoTableModel, PhotoTableView
from aim_tool.ui.preview_panel import PreviewPanel
from aim_tool.ui.settings_dialog import SettingsDialog
from aim_tool.ui.workers import BatchWorker, MetadataWorker, PreflightWorker
from aim_tool.ui.workflow_panel import WorkflowPanel
from aim_tool.workflow.engine import ExecutionPlan

STYLE = """
QMainWindow, QDialog { background: #edf2f7; }
QWidget { color: #1f3047; font-size: 13px; }
QWidget#card { background: white; border: 1px solid #dce4ee; border-radius: 12px; }
QFrame#stepCard { background: #f5f8fc; border: 1px solid #e4ebf3; border-radius: 9px; }
QLabel#brand { color: #0e7490; font-size: 25px; font-weight: 700; }
QLabel#title { color: #152c47; font-size: 23px; font-weight: 700; }
QLabel#sectionTitle { font-size: 15px; font-weight: 600; }
QLabel#muted { color: #64748b; font-size: 12px; }
QLabel#stepNumber { color: #0e7490; font-size: 18px; font-weight: 600; }
QPushButton { background: white; border: 1px solid #ced9e6; border-radius: 7px; padding: 7px 12px; }
QPushButton:hover { background: #f0f8fc; border-color: #69b4ca; }
QPushButton:pressed { background: #dceff7; }
QPushButton#primary { background: #0e7490; color: white; border-color: #0e7490; font-weight: 600; }
QPushButton#primary:hover { background: #09647d; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border-color: #e2e8f0; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; border: 1px solid #ced9e6; border-radius: 6px; padding: 6px; min-height: 18px; }
QLineEdit:focus, QComboBox:focus { border-color: #0e7490; }
QTableView { background: white; alternate-background-color: #f8fafc; border: 0; gridline-color: #eaf0f6; selection-background-color: #e0f2fe; selection-color: #164e63; }
QHeaderView::section { background: #f0f5fa; color: #4b617b; padding: 10px 6px; border: 0; border-bottom: 1px solid #dce4ee; font-weight: 600; }
QPlainTextEdit { background: #f8fafc; border: 1px solid #dce4ee; border-radius: 8px; padding: 6px; }
QProgressBar { background: #e6edf4; border: 0; border-radius: 4px; min-height: 9px; max-height: 12px; }
QProgressBar::chunk { background: #0891b2; border-radius: 4px; }
QSplitter::handle { background: transparent; }
QCheckBox { spacing: 7px; }
QTabWidget::pane { background: white; border: 1px solid #dce4ee; }
QTabBar::tab { padding: 10px 16px; background: #e5edf5; }
QTabBar::tab:selected { background: white; color: #0e7490; }
"""


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings_store: WatermarkSettingsStore | None = None,
        location_store: ConfigStore | None = None,
        workflow_store: ConfigStore | None = None,
        allow_nef_after_viewer_check: bool = True,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Auto Image Mark Tool")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(STYLE)
        self.setAcceptDrops(True)
        self.allow_nef_after_viewer_check = allow_nef_after_viewer_check
        self.settings_store = settings_store or WatermarkSettingsStore()
        initial_error = ""
        try:
            self.settings = self.settings_store.load()
        except (OSError, ValueError) as error:
            self.settings = WatermarkSettings(default_local_resources())
            initial_error = f"个人默认无法读取：{error}。当前临时使用项目默认，请在设置中恢复备份；损坏文件未改动。"
        self._preflight_worker: PreflightWorker | None = None
        self._batch_worker: BatchWorker | None = None
        self._metadata_worker: MetadataWorker | None = None
        self._metadata_pending: list[PhotoItem] = []
        self._closing = False
        self._busy = False
        self._execute_after_check = False
        self._completed_ids: set[str] = set()
        self.results: tuple[ItemResult, ...] = ()
        self.last_plan: ExecutionPlan | None = None

        self.model = PhotoTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.table = PhotoTableView()
        self.table.setModel(self.proxy)
        self.table.setColumnWidth(self.model.CHECK, 48)
        for column, width in (
            (self.model.FILE, 180),
            (self.model.CATEGORY, 75),
            (self.model.SUBJECT, 160),
            (self.model.DATE, 115),
            (self.model.DATE_SOURCE, 80),
            (self.model.LATITUDE, 110),
            (self.model.LONGITUDE, 110),
            (self.model.STATUS, 90),
            (self.model.OUTPUT, 220),
        ):
            self.table.setColumnWidth(column, width)
        table_header = self.table.horizontalHeader()
        table_header.moveSection(table_header.visualIndex(self.model.STATUS), 2)
        self.table.files_dropped.connect(self.add_photos)
        self.table.selectionModel().currentRowChanged.connect(self._schedule_preview)
        self.model.edited.connect(self._schedule_preview)
        self.model.edited.connect(self._update_count)
        self.model.rowsInserted.connect(self._update_count)
        self.model.rowsRemoved.connect(self._update_count)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索文件名、内容或状态")
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.counter = QLabel("0 张照片")
        self.counter.setObjectName("muted")
        self.add_button = QPushButton("添加照片")
        self.folder_button = QPushButton("添加文件夹")
        self.import_button = QPushButton("导入表格")
        self.paste_button = QPushButton("粘贴表格")
        self.remove_button = QPushButton("移除")
        self.add_button.clicked.connect(self._pick_files)
        self.folder_button.clicked.connect(self._pick_folder)
        self.import_button.clicked.connect(lambda: self.import_table())
        self.paste_button.clicked.connect(lambda: self.import_table(clipboard=True))
        self.remove_button.clicked.connect(self.remove_selected)
        file_controls = QHBoxLayout()
        for button in (
            self.add_button,
            self.folder_button,
            self.import_button,
            self.paste_button,
            self.remove_button,
        ):
            file_controls.addWidget(button)
        file_controls.addStretch()
        search_row = QHBoxLayout()
        search_row.addWidget(self.counter)
        search_row.addStretch()
        search_row.addWidget(self.search)
        self.bulk_category = QComboBox()
        for key, name in CATEGORIES.items():
            self.bulk_category.addItem(name, key)
        self.bulk_subject = QLineEdit()
        self.bulk_subject.setPlaceholderText("注册号 / 车号 / 风光内容")
        self.bulk_date = QLineEdit()
        self.bulk_date.setPlaceholderText("日期留空使用原 EXIF；或 YYYY-MM-DD")
        self.apply_fields_button = QPushButton("应用到勾选")
        self.apply_fields_button.clicked.connect(self.apply_bulk_fields)
        self.bulk_category.currentIndexChanged.connect(self._schedule_preview)
        field_controls = QHBoxLayout()
        field_controls.addWidget(self.bulk_category)
        field_controls.addWidget(self.bulk_subject, 1)
        field_controls.addWidget(self.bulk_date, 1)
        field_controls.addWidget(self.apply_fields_button)
        self.fields_widget = QWidget()
        self.fields_widget.setLayout(field_controls)
        field_controls.setContentsMargins(0, 0, 0, 0)
        self.photo_card = QWidget()
        self.photo_card.setObjectName("card")
        photos_layout = QVBoxLayout(self.photo_card)
        photos_layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("照片与逐行信息")
        title.setObjectName("sectionTitle")
        photos_layout.addWidget(title)
        photos_layout.addLayout(file_controls)
        photos_layout.addLayout(search_row)
        photos_layout.addWidget(self.fields_widget)
        photos_layout.addWidget(self.table, 1)
        table_hint = QLabel("可拖入 JPG；勾选控制处理范围，选中行控制预览。双击单元格可逐张编辑。")
        table_hint.setWordWrap(True)
        table_hint.setObjectName("muted")
        photos_layout.addWidget(table_hint)
        self.workflow = WorkflowPanel(workflow_store)
        self.workflow.changed.connect(self._workflow_changed)
        self.workflow.loaded.connect(self._load_params)
        self.workflow.save_requested.connect(self._save_workflow)
        self.workflow.message.connect(self._message)
        self.preview = PreviewPanel()
        self.preview.setObjectName("card")
        self.preview.moved.connect(self._move_watermark)
        self.preview.idle.connect(self._finish_close)
        self.splitter = QSplitter()
        self.splitter.addWidget(self.workflow)
        self.splitter.addWidget(self.photo_card)
        self.splitter.addWidget(self.preview)
        self.splitter.setSizes([210, 760, 420])
        self.splitter.setChildrenCollapsible(False)
        self.location_panel = LocationPanel(location_store, self)
        self.location_panel.apply_requested.connect(self.apply_coordinates)
        self.location_panel.message.connect(self._message)
        self.latitude = QLineEdit()
        self.latitude.setPlaceholderText("纬度 -90…90")
        self.longitude = QLineEdit()
        self.longitude.setPlaceholderText("经度 -180…180")
        self.coordinate_button = QPushButton("应用坐标到勾选")
        self.coordinate_button.clicked.connect(self.apply_coordinate_fields)
        self.clear_auxiliary = QCheckBox("允许清除旧高度等附属 GPS")
        self.clear_auxiliary.setToolTip("只影响输出副本；已有附属 GPS 时须明确选择后才能更新坐标。")
        coordinate_controls = QHBoxLayout()
        coordinate_controls.addWidget(QLabel("WGS84"))
        coordinate_controls.addWidget(self.latitude)
        coordinate_controls.addWidget(self.longitude)
        coordinate_controls.addWidget(self.coordinate_button)
        coordinate_controls.addWidget(self.clear_auxiliary)
        self.coordinates_card = QWidget()
        self.coordinates_card.setObjectName("card")
        coordinates_layout = QVBoxLayout(self.coordinates_card)
        coordinates_layout.setContentsMargins(16, 12, 16, 12)
        coordinates_layout.addWidget(self.location_panel)
        coordinates_layout.addLayout(coordinate_controls)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择与原片目录不同的输出文件夹")
        self.output_button = QPushButton("浏览")
        self.output_button.clicked.connect(self._pick_output)
        self.check_button = QPushButton("检查批次")
        self.start_button = QPushButton("开始处理")
        self.start_button.setObjectName("primary")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.retry_button = QPushButton("勾选失败项")
        self.retry_button.setEnabled(False)
        self.report_button = QPushButton("导出报告")
        self.report_button.setEnabled(False)
        self.check_button.clicked.connect(lambda: self.preflight())
        self.start_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        self.retry_button.clicked.connect(self.model.retry_failed)
        self.report_button.clicked.connect(self.export_report)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("输出目录"))
        output_row.addWidget(self.output_edit, 1)
        for button in (
            self.output_button,
            self.check_button,
            self.start_button,
            self.cancel_button,
        ):
            output_row.addWidget(button)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.status = QLabel("准备就绪 · 原片保持不变")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMaximumHeight(120)
        self.log.hide()
        log_button = QPushButton("作业日志")
        log_button.clicked.connect(lambda: self.log.setVisible(not self.log.isVisible()))
        summary_row = QHBoxLayout()
        summary_row.addWidget(self.status, 1)
        for button in (self.retry_button, self.report_button, log_button):
            summary_row.addWidget(button)
        footer = QWidget()
        footer.setObjectName("card")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addLayout(output_row)
        footer_layout.addWidget(self.progress)
        footer_layout.addLayout(summary_row)
        footer_layout.addWidget(self.log)
        brand = QLabel("AIM")
        brand.setObjectName("brand")
        heading = QLabel("照片批处理")
        heading.setObjectName("title")
        subtitle = QLabel("JPG 水印 / 坐标 · NEF 仅坐标 · 本地处理")
        subtitle.setObjectName("muted")
        heading_group = QVBoxLayout()
        heading_group.addWidget(heading)
        heading_group.addWidget(subtitle)
        self.settings_button = QPushButton("水印设置")
        self.settings_button.clicked.connect(self.open_settings)
        about = QPushButton("关于")
        about.clicked.connect(lambda: AboutDialog(self).exec())
        header = QHBoxLayout()
        header.addWidget(brand)
        header.addSpacing(16)
        header.addLayout(heading_group)
        header.addStretch()
        header.addWidget(self.settings_button)
        header.addWidget(about)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(self.splitter, 1)
        layout.addWidget(self.coordinates_card)
        layout.addWidget(footer)
        self.setCentralWidget(container)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self._request_preview)
        self._refresh_date_policy()
        self._workflow_changed()
        for message in (
            initial_error,
            self.location_panel.initial_error,
            self.workflow.initial_error,
        ):
            if message:
                self._message(message)

    @property
    def has_active_workers(self) -> bool:
        return any(
            (self._batch_worker, self._preflight_worker, self._metadata_worker, self.preview.busy)
        )

    def _message(self, message: str) -> None:
        self.log.appendPlainText(message)
        self.status.setText(message)
        self.status.setToolTip(message)
        self.status.setStyleSheet("color:#b91c1c;" if message.startswith("检查未通过") else "")

    def _update_count(self) -> None:
        count = sum(row.checked for row in self.model.rows)
        self.counter.setText(f"{len(self.model.rows)} 张照片 · 勾选 {count} 张")

    def _workflow_changed(self) -> None:
        watermark, location = (
            self.workflow.watermark.isChecked(),
            self.workflow.location.isChecked(),
        )
        self.fields_widget.setVisible(watermark)
        self.coordinates_card.setVisible(location)
        for column in (
            self.model.CATEGORY,
            self.model.SUBJECT,
            self.model.DATE,
            self.model.DATE_SOURCE,
        ):
            self.table.setColumnHidden(column, not watermark)
        for column in (self.model.LATITUDE, self.model.LONGITUDE):
            self.table.setColumnHidden(column, not location)
        self._schedule_preview()

    def _pick_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self, "添加照片", "", "照片 (*.jpg *.jpeg *.JPG *.JPEG *.nef *.NEF)"
        )
        self.add_photos(tuple(Path(name) for name in names))

    def _pick_folder(self) -> None:
        name = QFileDialog.getExistingDirectory(self, "添加照片文件夹")
        if name:
            root = Path(name)
            self.add_photos(
                tuple(
                    path
                    for path in root.rglob("*")
                    if path.suffix.lower() in {".jpg", ".jpeg", ".nef"}
                ),
                import_root=root,
            )

    def _pick_output(self) -> None:
        name = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if name:
            self.output_edit.setText(name)

    def add_photos(self, paths: Sequence[Path], *, import_root: Path | None = None) -> None:
        if self._busy or self._closing:
            return
        files: list[Path] = []
        for path in paths:
            if path.is_dir():
                files.extend(
                    candidate
                    for candidate in path.rglob("*")
                    if candidate.suffix.lower() in {".jpg", ".jpeg", ".nef"}
                )
            else:
                files.append(path)
        added = self.model.add_paths(files, import_root)
        self._metadata_pending.extend(added)
        self._start_metadata()
        if self.table.currentIndex().isValid() is False and self.proxy.rowCount():
            self.table.selectRow(0)
        self._message(f"已添加 {len(added)} 张照片；NEF 仅可选择坐标流程。")
        self._update_count()

    def _start_metadata(self) -> None:
        if self._metadata_worker is not None or not self._metadata_pending or self._closing:
            return
        worker = MetadataWorker(tuple(self._metadata_pending), self)
        self._metadata_pending.clear()
        self._metadata_worker = worker
        worker.ready.connect(self._metadata_ready)
        worker.error.connect(self._message)
        worker.finished.connect(self._metadata_finished)
        worker.start()

    def _metadata_ready(self, photo_id: str, metadata: dict[str, str]) -> None:
        self.model.update_metadata(UUID(photo_id), metadata)
        if self.table.currentIndex().data(Qt.ItemDataRole.UserRole) == photo_id:
            self._schedule_preview()

    def _metadata_finished(self) -> None:
        if self._metadata_worker is not None:
            self._metadata_worker.deleteLater()
        self._metadata_worker = None
        self._start_metadata()
        self._finish_close()

    def remove_selected(self) -> None:
        ids = {
            UUID(index.data(Qt.ItemDataRole.UserRole))
            for index in self.table.selectionModel().selectedRows()
        }
        self.model.remove_ids(ids)
        self._schedule_preview()
        self._update_count()

    def _photos(
        self, *, selected: bool = False, checked_only: bool = True
    ) -> tuple[PhotoItem, ...]:
        ids = None
        if selected:
            current = self.table.currentIndex()
            ids = {UUID(current.data(Qt.ItemDataRole.UserRole))} if current.isValid() else set()
        photos = self.model.snapshot(checked_only=checked_only, ids=ids)
        if self.workflow.watermark.isChecked():
            photos = tuple(
                replace(
                    photo,
                    edits={
                        **photo.edits,
                        "category": photo.edits.get("category")
                        or str(self.bulk_category.currentData()),
                    },
                )
                for photo in photos
            )
        return photos

    def apply_bulk_fields(self) -> None:
        try:
            photos = self.model.snapshot()
            if not photos:
                raise ValueError("请勾选照片")
            if self.bulk_date.text().strip():
                parse_capture_date(self.bulk_date.text())
            updated = []
            for photo in photos:
                edits = dict(photo.edits)
                edits["category"] = str(self.bulk_category.currentData())
                if self.bulk_subject.text().strip():
                    edits["subject"] = self.bulk_subject.text().strip()
                photo = replace(photo, edits=edits)
                if self.bulk_date.text().strip():
                    photo = apply_manual_date(photo, self.bulk_date.text())
                    photo = replace(
                        photo,
                        edits={
                            key: value for key, value in photo.edits.items() if key != "date_input"
                        },
                    )
                updated.append(photo)
            self.model.update_photos(updated)
        except ValueError as error:
            self._message(f"信息未应用：{error}")
            return
        self._message(f"已应用信息到 {len(updated)} 张勾选照片。")

    def apply_coordinates(self, latitude: float, longitude: float) -> None:
        try:
            validate_coordinates(latitude, longitude)
            rows = [row for row in self.model.rows if row.checked]
            if not rows:
                raise ValueError("请勾选照片")
            updated = []
            for row in rows:
                edits = {
                    key: value
                    for key, value in row.photo.edits.items()
                    if key not in {"latitude_input", "longitude_input"}
                }
                updated.append(replace(row.photo, edits=edits, coordinates=(latitude, longitude)))
            self.model.update_photos(updated)
        except ValueError as error:
            self._message(f"坐标未应用：{error}")
            return
        self.latitude.setText(str(latitude))
        self.longitude.setText(str(longitude))
        self._message(f"已应用坐标到 {len(updated)} 张勾选照片。")

    def apply_coordinate_fields(self) -> None:
        try:
            self.apply_coordinates(float(self.latitude.text()), float(self.longitude.text()))
        except ValueError as error:
            self._message(f"坐标无效：{error}")

    def import_table(self, *, clipboard: bool = False) -> None:
        try:
            photos = self.model.snapshot(checked_only=False)
            if not photos:
                raise ValueError("请先添加照片")
        except ValueError as error:
            self._message(str(error))
            return
        dialog = ImportDialog(photos, self, clipboard=clipboard)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.preview is not None:
            updated = apply_import(dialog.preview, photos)
            matches = {match.photo_id: match.row.values for match in dialog.preview.matches}
            cleaned = []
            for photo in updated:
                edits = dict(photo.edits)
                if "latitude" in matches.get(photo.id, {}):
                    edits.pop("latitude_input", None)
                    edits.pop("longitude_input", None)
                cleaned.append(replace(photo, edits=edits))
            self.model.update_photos(cleaned)
            self._message(f"表格已应用到 {len(dialog.preview.matches)} 张照片。")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.settings_store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings()
            self._refresh_date_policy()
            self._schedule_preview()
            self._message("已应用水印设置；导出仍需点击开始处理。")

    def _load_params(self, params: Mapping[str, Parameter]) -> None:
        self.settings = WatermarkSettings(self.settings.resources, params)
        self._refresh_date_policy()
        self._schedule_preview()

    def _refresh_date_policy(self) -> None:
        self.model.allow_create_date = self.settings.params.get("allow_create_date") is True
        for row in range(self.model.rowCount()):
            self.model.dataChanged.emit(
                self.model.index(row, self.model.DATE),
                self.model.index(row, self.model.DATE_SOURCE),
                [],
            )

    def _save_workflow(self, name: str) -> None:
        try:
            self.workflow.save(name, self.workflow.spec(self.settings.params))
            self._message(f"已保存流程预设：{name}")
        except (OSError, ValueError) as error:
            self._message(f"保存流程失败：{error}")

    def _schedule_preview(self) -> None:
        if not self._closing and not self._busy:
            self._preview_timer.start()

    def _request_preview(self) -> None:
        if self._closing or self._busy:
            return
        try:
            photos = self._photos(selected=True, checked_only=False)
            if not photos:
                self.preview.invalidate("选择一张 JPG 查看预览。")
                return
            if photos[0].source.suffix.lower() == ".nef":
                self.preview.invalidate("NEF 仅写入坐标，保留原格式；本版不显影或生成 JPG 预览。")
                return
            self.preview.request(
                photos[0], self.settings if self.workflow.watermark.isChecked() else None
            )
        except (OSError, ValueError) as error:
            self.preview.invalidate(f"预览未通过：{error}")

    def _move_watermark(self, dx: float, dy: float) -> None:
        if self._busy or self.preview.last_result is None:
            return
        try:
            photo = self._photos(selected=True, checked_only=False)[0]
            # Only canvas dimensions are needed here; the actual renderer revalidates the result.
            config = project_default_config(
                "aviation", "TEST", photo.taken_on or parse_capture_date("2000-01-01")
            )
            scale = watermark_scale(self.preview.last_result.size, config)
            params = dict(self.settings.params)
            params["offset_x"] = float(str(params.get("offset_x", 0))) + dx / scale
            params["offset_y"] = float(str(params.get("offset_y", 0))) + dy / scale
            self.settings = WatermarkSettings(self.settings.resources, params)
            self._schedule_preview()
            self._message("水印位置已调整；可在水印设置中保存为我的默认。")
        except (ValueError, IndexError) as error:
            self._message(f"位置未调整：{error}")

    def preflight(self, *, execute: bool = False) -> None:
        if self._busy:
            return
        try:
            photos = self._photos()
            if not photos:
                raise ValueError("请勾选至少一张照片")
            if self.workflow.watermark.isChecked() and any(
                photo.source.suffix.lower() == ".nef" for photo in photos
            ):
                raise ValueError("NEF 仅支持坐标写入；请选择坐标流程或取消勾选 NEF。")
            if not self.output_edit.text().strip():
                raise ValueError("请选择输出目录")
            job = BatchJob(
                photos, self.workflow.spec(self.settings.params), Path(self.output_edit.text())
            )
        except (OSError, ValueError) as error:
            self._message(f"检查未通过：{error}")
            return
        self.last_plan = None
        self._execute_after_check = execute
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self._message(f"正在预检 {len(photos)} 张照片…")
        worker = PreflightWorker(
            job,
            self.settings,
            self,
            clear_auxiliary_gps=self.clear_auxiliary.isChecked(),
            allow_nef_after_viewer_check=self.allow_nef_after_viewer_check,
        )
        self._preflight_worker = worker
        worker.item_error.connect(self.model.preflight_error)
        worker.ready.connect(self._plan_ready)
        worker.error.connect(lambda message: self._message(f"检查未通过：{message}"))
        worker.finished.connect(self._preflight_finished)
        worker.start()

    def start(self) -> None:
        self.preflight(execute=True)

    def _plan_ready(self, plan: ExecutionPlan) -> None:
        if (
            self._closing
            or self._preflight_worker is None
            or self._preflight_worker.cancelled.is_set()
        ):
            return
        self.last_plan = plan
        self.progress.setRange(0, len(plan.items))
        self.progress.setValue(0)
        self._message(f"检查通过：{len(plan.items)} 张照片；原片保持不变。")
        if self._execute_after_check:
            self.results = ()
            self.report_button.setEnabled(False)
            self._completed_ids.clear()
            worker = BatchWorker(plan, self)
            self._batch_worker = worker
            worker.progress.connect(self._on_progress)
            worker.completed.connect(self._on_completed)
            worker.finished.connect(self._batch_finished)
            worker.start()

    def _preflight_finished(self) -> None:
        if self._preflight_worker is not None:
            self._preflight_worker.deleteLater()
        self._preflight_worker = None
        if self._batch_worker is None:
            self.progress.setRange(0, len(self.last_plan.items) if self.last_plan else 1)
            self._set_busy(False)
        self._finish_close()

    def _on_progress(self, photo_id: str, message: str) -> None:
        name = next(
            (row.photo.source.name for row in self.model.rows if str(row.photo.id) == photo_id),
            photo_id,
        )
        self._message(f"{name}：{message}")
        if message.startswith("Committed output"):
            self._completed_ids.add(photo_id)
            self.progress.setValue(len(self._completed_ids))

    def _on_completed(self, results: tuple[ItemResult, ...]) -> None:
        self.results = results
        self.model.mark_results(results)
        for result in results:
            for warning in result.warnings:
                self.log.appendPlainText(f"警告：{warning}")
            if result.error:
                self.log.appendPlainText(f"失败：{result.error}")
        succeeded = sum(result.status == ItemStatus.SUCCESS for result in results)
        failed = sum(result.status == ItemStatus.FAILED for result in results)
        cancelled = sum(result.status == ItemStatus.CANCELLED for result in results)
        self.progress.setRange(0, len(results))
        self.progress.setValue(len(results))
        self._message(f"完成：成功 {succeeded} · 失败 {failed} · 取消 {cancelled}")

    def _batch_finished(self) -> None:
        if self._batch_worker is not None:
            self._batch_worker.deleteLater()
        self._batch_worker = None
        self._set_busy(False)
        self.retry_button.setEnabled(
            any(result.status != ItemStatus.SUCCESS for result in self.results)
        )
        self.report_button.setEnabled(bool(self.results))
        self._finish_close()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (
            self.photo_card,
            self.workflow,
            self.coordinates_card,
            self.output_edit,
            self.output_button,
            self.check_button,
            self.start_button,
            self.settings_button,
            self.retry_button,
            self.report_button,
            self.preview,
        ):
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if busy:
            self._preview_timer.stop()
            self.preview.invalidate("批次处理中；预览已暂停。")
        else:
            self._schedule_preview()
            self.report_button.setEnabled(bool(self.results))
            self.retry_button.setEnabled(
                any(result.status != ItemStatus.SUCCESS for result in self.results)
            )

    def cancel(self) -> None:
        for worker in (self._preflight_worker, self._batch_worker):
            if worker is not None:
                worker.cancelled.set()
        self._message("已请求取消；当前不可中断操作结束后停止，未提交产物会清理。")

    def export_report(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "保存结果报告", "results.json", "JSON (*.json)")
        if name:
            self.save_report(Path(name))

    def save_report(self, path: Path) -> None:
        sources = {row.photo.id: row.photo.source for row in self.model.rows}
        data = [
            {
                "source": str(sources.get(result.photo_id, "")),
                "status": result.status.value,
                "output": str(result.output) if result.output else None,
                "step": result.current_step,
                "error": result.error,
                "warnings": result.warnings,
            }
            for result in self.results
        ]
        try:
            with path.open("x", encoding="utf-8") as target:
                target.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            self._message(f"已保存结果报告：{path}；未包含坐标字段。")
        except OSError as error:
            self._message(f"报告未保存：{error}")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not self._busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.add_photos(
            tuple(Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile())
        )
        event.acceptProposedAction()

    def _finish_close(self) -> None:
        if self._closing and not self.has_active_workers:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        self._preview_timer.stop()
        self._metadata_pending.clear()
        self.preview.shutdown()
        for worker in (self._preflight_worker, self._batch_worker, self._metadata_worker):
            if worker is not None:
                worker.cancelled.set()
        if self.has_active_workers:
            event.ignore()
        else:
            super().closeEvent(event)
