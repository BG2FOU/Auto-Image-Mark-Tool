"""Ordered built-in photo workflow cards and local preset persistence."""

from __future__ import annotations

from collections.abc import Mapping

from platformdirs import user_config_path
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QInputDialog,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import StepSpec, WorkflowSpec
from aim_tool.domain.models import Parameter
from aim_tool.services.storage import AppConfig, ConfigStore


class WorkflowPanel(QWidget):
    changed = Signal()
    loaded = Signal(object)
    save_requested = Signal(str)
    message = Signal(str)

    def __init__(self, store: ConfigStore | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store or ConfigStore(
            user_config_path("AutoImageMarkTool", "BG2FOU") / "workflows.json"
        )
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(190)
        self.setMaximumWidth(260)
        heading = QLabel("处理流程")
        heading.setObjectName("sectionTitle")
        self.presets = QComboBox()
        self.location = QCheckBox("写入坐标")
        self.watermark = QCheckBox("添加水印")
        self.location.setChecked(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("workflowContent")
        self.scroll_area.setWidget(self.content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll_area)
        layout = QVBoxLayout(self.content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(heading)
        layout.addWidget(self.presets)
        for number, control, hint in (
            ("01", self.location, "WGS84 十进制度\n写入副本并独立读回"),
            ("02", self.watermark, "按原图像素适配整组\n保留拍摄信息与当前 GPS"),
        ):
            card = QFrame()
            card.setObjectName("stepCard")
            content = QVBoxLayout(card)
            badge = QLabel(number)
            badge.setObjectName("stepNumber")
            description = QLabel(hint)
            description.setWordWrap(True)
            description.setObjectName("muted")
            content.addWidget(badge)
            content.addWidget(control)
            content.addWidget(description)
            layout.addWidget(card)
        export = QLabel("03  导出副本\n检查完整后提交，不覆盖原片")
        export.setWordWrap(True)
        export.setObjectName("muted")
        layout.addWidget(export)
        save = QPushButton("保存流程预设")
        save.clicked.connect(self._save_prompt)
        layout.addWidget(save)
        layout.addStretch()
        note = QLabel("JPG / JPEG：坐标与水印\nNEF：仅坐标，保留原格式")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        self._saved: dict[str, WorkflowSpec] = {}
        self.initial_error = ""
        try:
            self._saved = dict(self.store.load().workflows)
        except (ValueError, OSError) as error:
            self.initial_error = f"流程预设无法读取：{error}"
        self._refresh()
        self.presets.currentIndexChanged.connect(self._selected)
        self.location.toggled.connect(self._toggled)
        self.watermark.toggled.connect(self._toggled)
        self._text_sizes: tuple[int, ...] | None = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._fit_text)
        self.scroll_area.viewport().installEventFilter(self)
        self._resize_timer.start(0)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._resize_timer.start(0)
        return super().eventFilter(watched, event)

    def _fit_text(self) -> None:
        """Use smaller readable text, then scroll instead of crushing workflow cards."""
        viewport = self.scroll_area.viewport()
        scale = max(0.9, min(1.0, viewport.width() / 210, viewport.height() / 480))
        sizes = tuple(round(size * scale) for size in (13, 15, 12, 18))
        if sizes != self._text_sizes:
            self._text_sizes = sizes
            body, heading, muted, number = sizes
            self.content.setStyleSheet(
                f"QWidget {{ font-size: {body}px; }}"
                "QWidget#workflowContent { background: white; }"
                f"QLabel#sectionTitle {{ font-size: {heading}px; }}"
                f"QLabel#muted {{ font-size: {muted}px; }}"
                f"QLabel#stepNumber {{ font-size: {number}px; }}"
            )
        layout = self.content.layout()
        assert layout is not None
        # Include wrapped lines at the actual viewport width, including scrollbar space.
        # A font floor alone cannot fit an entire workflow into a short window.
        layout.invalidate()
        height = layout.totalHeightForWidth(viewport.width())
        self.content.setMinimumHeight(max(height, layout.minimumSize().height()))
        layout.activate()

    def _refresh(self) -> None:
        self.presets.blockSignals(True)
        self.presets.clear()
        for label, key in (("坐标", "location"), ("水印", "watermark"), ("坐标 + 水印", "both")):
            self.presets.addItem(label, key)
        for name in self._saved:
            self.presets.addItem(name, "saved:" + name)
        self.presets.blockSignals(False)

    def _selected(self) -> None:
        key = str(self.presets.currentData())
        if key.startswith("saved:"):
            try:
                spec = self._saved[key[6:]]
                if (
                    [step.component_id for step in spec.steps]
                    != ["location", "watermark", "export"]
                    or any(step.version != 1 for step in spec.steps)
                    or not spec.steps[-1].enabled
                    or not any(step.enabled for step in spec.steps[:2])
                ):
                    raise ValueError("此预设不是合法的工作流")
                self._set_steps(spec.steps[0].enabled, spec.steps[1].enabled)
                self.loaded.emit(spec.steps[1].params)
            except (KeyError, ValueError) as error:
                self.message.emit(f"流程预设未载入：{error}")
                return
        else:
            self._set_steps(key in {"location", "both"}, key in {"watermark", "both"})
        self.changed.emit()

    def _set_steps(self, location: bool, watermark: bool) -> None:
        for control, value in ((self.location, location), (self.watermark, watermark)):
            control.blockSignals(True)
            control.setChecked(value)
            control.blockSignals(False)

    def _toggled(self) -> None:
        key = (
            "both"
            if self.location.isChecked() and self.watermark.isChecked()
            else "location"
            if self.location.isChecked()
            else "watermark"
            if self.watermark.isChecked()
            else ""
        )
        self.presets.blockSignals(True)
        self.presets.setCurrentIndex(self.presets.findData(key))
        self.presets.blockSignals(False)
        self.changed.emit()

    def spec(self, params: Mapping[str, Parameter]) -> WorkflowSpec:
        if not self.location.isChecked() and not self.watermark.isChecked():
            raise ValueError("请启用坐标或水印步骤")
        return WorkflowSpec(
            (
                StepSpec("location", enabled=self.location.isChecked()),
                StepSpec("watermark", enabled=self.watermark.isChecked(), params=params),
                StepSpec("export"),
            )
        )

    def _save_prompt(self) -> None:
        name, confirmed = QInputDialog.getText(self, "保存流程预设", "预设名称")
        if confirmed and name.strip():
            self.save_requested.emit(name.strip())

    def save(self, name: str, spec: WorkflowSpec) -> None:
        current = self.store.load()
        workflows = dict(current.workflows)
        workflows[name] = spec
        self.store.save(AppConfig(workflows, current.locations))
        self._saved = workflows
        self._refresh()
        self.presets.setCurrentIndex(self.presets.findData("saved:" + name))
