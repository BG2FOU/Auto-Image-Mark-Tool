"""Asynchronous table preview, explicit header mapping and apply confirmation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import PhotoItem
from aim_tool.services.table_import import FIELDS, ImportPreview
from aim_tool.ui.workers import TableImportWorker


class ImportDialog(QDialog):
    def __init__(
        self,
        photos: tuple[PhotoItem, ...],
        parent: QWidget | None = None,
        *,
        clipboard: bool = False,
    ) -> None:
        super().__init__(parent)
        self.photos = photos
        self.preview: ImportPreview | None = None
        self._worker: TableImportWorker | None = None
        self._closing = False
        self.setWindowTitle("导入表格 · 预览匹配")
        self.resize(900, 650)
        self.tabs = QTabWidget()
        file_page = QWidget()
        file_form = QFormLayout(file_page)
        self.path = QLineEdit()
        browse = QPushButton("浏览")
        browse.clicked.connect(self._pick_file)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)
        file_form.addRow("CSV / TSV / XLSX", path_row)
        self.encoding = QComboBox()
        self.encoding.addItem("UTF-8 / UTF-8 BOM", "utf-8-sig")
        self.encoding.addItem("GB18030（明确选择）", "gb18030")
        file_form.addRow("文本编码", self.encoding)
        self.sheet = QLineEdit()
        self.sheet.setPlaceholderText("留空使用首个工作表")
        file_form.addRow("XLSX 工作表", self.sheet)
        self.tabs.addTab(file_page, "表格文件")
        self.pasted = QPlainTextEdit()
        self.pasted.setPlaceholderText(
            "从 Excel 复制包含表头的单元格，粘贴到这里。字段以制表符分隔。"
        )
        self.tabs.addTab(self.pasted, "粘贴 TSV")
        if clipboard:
            self.tabs.setCurrentIndex(1)
            self.pasted.setPlainText(QGuiApplication.clipboard().text())
        self.mapping = QPlainTextEdit()
        self.mapping.setMaximumHeight(70)
        self.mapping.setPlaceholderText(
            "可选列映射，每行 原表头=标准字段。例如：照片名称=file_name；编号=subject（分两行填写）"
        )
        self.summary = QLabel(
            "支持中文标准表头。类别使用 aviation / railway / landscape；空单元格不覆盖已有字段。"
        )
        self.summary.setWordWrap(True)
        field_hint = QLabel("标准字段：" + ", ".join(FIELDS))
        field_hint.setWordWrap(True)
        field_hint.setObjectName("muted")
        self.table = QTableWidget(0, len(FIELDS))
        self.table.setHorizontalHeaderLabels(FIELDS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.check_button = QPushButton("生成匹配预览")
        self.check_button.clicked.connect(self.generate_preview)
        self.apply_button = QPushButton("应用已确认的匹配")
        self.apply_button.setObjectName("primary")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.apply_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.mapping)
        layout.addWidget(field_hint)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)
        for edit in (self.path, self.sheet):
            edit.textChanged.connect(self._invalidate)
        self.pasted.textChanged.connect(self._invalidate)
        self.mapping.textChanged.connect(self._invalidate)
        self.tabs.currentChanged.connect(self._invalidate)
        self.encoding.currentIndexChanged.connect(self._invalidate)

    def _invalidate(self) -> None:
        self.preview = None
        self.apply_button.setEnabled(False)

    def _pick_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "选择表格", "", "表格 (*.csv *.tsv *.xlsx)")
        if filename:
            self.path.setText(filename)

    def generate_preview(self) -> None:
        if self._worker is not None:
            return
        self._invalidate()
        try:
            mapping = {}
            for line in self.mapping.toPlainText().splitlines():
                if not line.strip():
                    continue
                alias, field = line.split("=", 1)
                if alias.strip() in mapping:
                    raise ValueError("映射中有重复表头")
                mapping[alias.strip()] = field.strip()
            path = Path(self.path.text().strip()) if self.tabs.currentIndex() == 0 else None
            worker = TableImportWorker(
                self.photos,
                path=path,
                text=self.pasted.toPlainText(),
                encoding=str(self.encoding.currentData()),
                sheet=self.sheet.text().strip() or None,
                mapping=mapping,
                parent=self,
            )
        except ValueError as error:
            self.summary.setText(f"映射无效：{error}")
            return
        self._worker = worker
        self.tabs.setEnabled(False)
        self.mapping.setEnabled(False)
        self.check_button.setEnabled(False)
        self.summary.setText("正在读取与匹配…")
        worker.ready.connect(self._ready)
        worker.error.connect(lambda message: self.summary.setText(f"导入未通过：{message}"))
        worker.finished.connect(self._finished)
        worker.start()

    def _ready(self, preview: ImportPreview) -> None:
        if self._closing:
            return
        self.preview = preview
        self.table.setRowCount(len(preview.matches))
        for number, match in enumerate(preview.matches):
            for column, key in enumerate(FIELDS):
                self.table.setItem(
                    number, column, QTableWidgetItem(str(match.row.values.get(key, "")))
                )
        self.summary.setText(
            "\n".join(preview.errors)
            if preview.errors
            else f"已唯一匹配 {len(preview.matches)} 张照片；确认后应用。"
        )
        self.apply_button.setEnabled(bool(preview.matches) and not preview.errors)

    def _finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        if self._closing:
            self.close()
        else:
            self.tabs.setEnabled(True)
            self.mapping.setEnabled(True)
            self.check_button.setEnabled(True)

    def _apply(self) -> None:
        if (
            self._worker is None
            and self.preview is not None
            and self.preview.matches
            and not self.preview.errors
        ):
            self.accept()

    def reject(self) -> None:
        if self._worker is not None:
            self._closing = True
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._closing = True
            event.ignore()
            return
        super().closeEvent(event)
