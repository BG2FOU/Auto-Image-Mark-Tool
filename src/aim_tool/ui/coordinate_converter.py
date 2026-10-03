"""Offline batch conversion with a reviewed preview before saving WGS84 presets."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import LocationPreset
from aim_tool.services.coordinate_conversion import (
    CoordinateRow,
    Direction,
    convert_row,
    coordinate_csv,
    parse_coordinate_rows,
)
from aim_tool.services.storage import AppConfig, ConfigStore


class ConversionWorker(QThread):
    ready = Signal(object)
    error = Signal(str)

    def __init__(self, text: str, direction: Direction, parent: QWidget) -> None:
        super().__init__(parent)
        self.text = text
        self.direction = direction

    def run(self) -> None:
        try:
            rows = parse_coordinate_rows(self.text, self.direction)
            result = []
            for row in rows:
                if self.isInterruptionRequested():
                    return
                result.append(convert_row(row, self.direction))
            if not self.isInterruptionRequested():
                self.ready.emit(tuple(result))
        except ValueError as error:
            self.error.emit(str(error))


class CoordinateConverterDialog(QDialog):
    locations_saved = Signal()

    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.rows: tuple[CoordinateRow, ...] = ()
        self._worker: ConversionWorker | None = None
        self._closing = False
        self._saved_preview = False
        self.setWindowTitle("小工具 · 批量坐标转换")
        self.resize(850, 680)
        self.direction = QComboBox()
        self.direction.addItem("GCJ-02 → WGS84（用于坐标列表）", "gcj_to_wgs")
        self.direction.addItem("WGS84 → GCJ-02（仅复制或导出）", "wgs_to_gcj")
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "名称,纬度,经度,海拔\n地点1,39.91334545536069,116.38404722455657,0\n\n支持 Excel 制表符粘贴或 UTF-8 CSV/TSV，海拔可省略；最多 10000 行。"
        )
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.status = QLabel("选择正确的输入坐标系，再转换并检查结果。")
        self.status.setWordWrap(True)
        self.convert_button = QPushButton("转换并预览")
        self.convert_button.setObjectName("primary")
        self.import_button = QPushButton("导入 CSV / TSV")
        self.copy_button = QPushButton("复制结果")
        self.export_button = QPushButton("导出 CSV")
        self.save_button = QPushButton("追加到 WGS84 坐标列表")
        self.convert_button.clicked.connect(self.convert)
        self.import_button.clicked.connect(self.import_file)
        self.copy_button.clicked.connect(self.copy_results)
        self.export_button.clicked.connect(self.export_file)
        self.save_button.clicked.connect(self.save_locations)
        self.input.textChanged.connect(self.invalidate)
        self.direction.currentIndexChanged.connect(self.invalidate)
        explanation = QLabel(
            "离线近似算法，非官方变换；迭代逆解不代表真实测量精度。矩形适用范围外保持原值，边界附近请核对。海拔不转换，留空为 0。"
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("muted")
        commands = QHBoxLayout()
        commands.addWidget(self.direction, 1)
        commands.addWidget(self.import_button)
        commands.addWidget(self.convert_button)
        actions = QHBoxLayout()
        for button in (self.copy_button, self.export_button, self.save_button):
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(commands)
        layout.addWidget(explanation)
        layout.addWidget(QLabel("输入：纬度在经度前；无名称时自动编号。"))
        layout.addWidget(self.input, 1)
        layout.addWidget(QLabel("结果预览："))
        layout.addWidget(self.output, 1)
        layout.addWidget(self.status)
        layout.addLayout(actions)
        self.invalidate()

    def selected_direction(self) -> Direction:
        return cast(Direction, self.direction.currentData())

    def invalidate(self) -> None:
        self.rows = ()
        self._saved_preview = False
        self.output.clear()
        for button in (self.copy_button, self.export_button, self.save_button):
            button.setEnabled(False)
        self.status.setText("输入或方向已改变，请重新转换；不会自动修改坐标列表。")

    def convert(self) -> None:
        if self._worker is not None:
            return
        self.invalidate()
        worker = ConversionWorker(self.input.toPlainText(), self.selected_direction(), self)
        self._worker = worker
        for control in (self.direction, self.input, self.convert_button, self.import_button):
            control.setEnabled(False)
        worker.ready.connect(self._ready)
        worker.error.connect(self.status.setText)
        worker.finished.connect(self._finished)
        self.status.setText("正在转换…")
        worker.start()

    def _ready(self, rows: tuple[CoordinateRow, ...]) -> None:
        if self._closing:
            return
        self.rows = rows
        self.output.setPlainText(coordinate_csv(rows, self.selected_direction()))
        self.copy_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.save_button.setEnabled(self.selected_direction() == "gcj_to_wgs")
        self.status.setText(f"已转换 {len(rows)} 个地点；检查结果后可复制、导出或追加 WGS84 列表。")

    def _finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        for control in (self.direction, self.input, self.convert_button, self.import_button):
            control.setEnabled(True)
        if self._closing:
            self.close()

    def save_locations(self) -> None:
        if (
            not self.rows
            or self.selected_direction() != "gcj_to_wgs"
            or self._worker is not None
            or self._saved_preview
        ):
            return
        try:
            config = self.store.load()
            new = tuple(
                LocationPreset(row.name, row.latitude, row.longitude, altitude=row.altitude)
                for row in self.rows
            )
            self.store.save(AppConfig(config.workflows, (*config.locations, *new)))
        except (OSError, ValueError) as error:
            self.status.setText(f"保存失败：{error}；原列表未覆盖。")
            return
        self.save_button.setEnabled(False)
        self.status.setText(f"已追加 {len(new)} 个 WGS84 地点；原地点保留。")
        self._saved_preview = True
        self.locations_saved.emit()

    def import_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "导入坐标", "", "坐标表 (*.csv *.tsv)")
        if filename:
            try:
                path = Path(filename)
                if path.stat().st_size > 5_000_000:
                    raise ValueError("文件超过 5 MB，请拆分批次")
                self.input.setPlainText(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as error:
                self.status.setText(f"导入失败：{error}")

    def copy_results(self) -> None:
        if self.rows:
            QApplication.clipboard().setText(coordinate_csv(self.rows, self.selected_direction()))

    def export_file(self) -> None:
        if not self.rows:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出转换结果", "coordinates.csv", "CSV (*.csv)"
        )
        if filename:
            try:
                Path(filename).write_text(
                    coordinate_csv(self.rows, self.selected_direction()), encoding="utf-8-sig"
                )
            except (OSError, ValueError) as error:
                self.status.setText(f"导出失败：{error}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._closing = True
            self._worker.requestInterruption()
            event.ignore()
        else:
            event.accept()

    def reject(self) -> None:
        # Escape must obey the same worker shutdown rule as the window close button.
        if self._worker is not None:
            self._closing = True
            self._worker.requestInterruption()
        else:
            super().reject()
