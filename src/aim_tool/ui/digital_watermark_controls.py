"""The same signature-watermark selectors in the workflow card and settings."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from aim_tool.domain.models import Parameter


class DigitalWatermarkControls(QWidget):
    changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.enabled = QCheckBox("附加频域水印")
        self.enabled.setToolTip("将本地签名嵌入照片像素；随添加水印步骤一起导出。")
        self.algorithm = QComboBox()
        for label, value in (("DCT", "dct"), ("FFT", "fft")):
            self.algorithm.addItem(label, value)
        self.algorithm.setToolTip("DCT 较侧重画质；FFT 在已测试的辅助缩放恢复中表现较好。")
        self.level = QComboBox()
        for label, value in (("低档", "low"), ("中档", "medium"), ("高档", "high")):
            self.level.addItem(label, value)
        self.level.setToolTip("档位越高，像素变化通常越大；请根据成片画质选择。")
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.enabled)
        form.addRow("算法", self.algorithm)
        form.addRow("档位", self.level)
        self.set_parameters({})
        self.enabled.toggled.connect(self._changed)
        self.algorithm.currentIndexChanged.connect(self._changed)
        self.level.currentIndexChanged.connect(self._changed)

    def set_parameters(self, params: Mapping[str, Parameter]) -> None:
        enabled = params.get("digital_enabled", True)
        algorithm = self.algorithm.findData(params.get("digital_algorithm", "dct"))
        level = self.level.findData(params.get("digital_level", "medium"))
        if type(enabled) is not bool or algorithm < 0 or level < 0:
            raise ValueError("频域水印设置无效")
        for control in (self.enabled, self.algorithm, self.level):
            control.blockSignals(True)
        self.enabled.setChecked(enabled)
        self.algorithm.setCurrentIndex(algorithm)
        self.level.setCurrentIndex(level)
        for control in (self.enabled, self.algorithm, self.level):
            control.blockSignals(False)
        self._sync_enabled()

    def parameters(self) -> dict[str, Parameter]:
        return {
            "digital_enabled": self.enabled.isChecked(),
            "digital_algorithm": str(self.algorithm.currentData()),
            "digital_level": str(self.level.currentData()),
        }

    def _sync_enabled(self) -> None:
        self.algorithm.setEnabled(self.enabled.isChecked())
        self.level.setEnabled(self.enabled.isChecked())

    def _changed(self) -> None:
        self._sync_enabled()
        self.changed.emit(self.parameters())
