"""Local font/signature selection and explicit personal watermark defaults."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain.models import Parameter
from aim_tool.services.fonts import identify_font
from aim_tool.services.resources import default_local_resources, identify_signature
from aim_tool.services.storage import WatermarkSettings, WatermarkSettingsStore
from aim_tool.services.templates import project_default_config
from aim_tool.services.watermark import WatermarkResources


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: WatermarkSettings,
        store: WatermarkSettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("水印设置")
        self.resize(650, 610)
        self.tabs = QTabWidget()
        self.assets: dict[str, QLineEdit] = {}
        self.faces: dict[str, QSpinBox] = {}
        self.numbers: dict[str, QDoubleSpinBox] = {}
        assets_page = QWidget()
        asset_form = QFormLayout(assets_page)
        note = QLabel("字体与签名在本机选择。程序只保存路径，公开安装包不包含这些素材。")
        note.setWordWrap(True)
        asset_form.addRow(note)
        for key, label in (
            ("latin_font", "英文 / 数字字体"),
            ("chinese_font", "中文字体"),
            ("signature", "透明签名 PNG"),
        ):
            edit = QLineEdit()
            edit.setPlaceholderText("选择本地文件…")
            button = QPushButton("浏览")
            button.clicked.connect(lambda checked=False, name=key: self._pick_asset(name))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            self.assets[key] = edit
            asset_form.addRow(label, row)
            if key != "signature":
                face = QSpinBox()
                face.setRange(0, 100)
                face.setToolTip("TTC 字体集合的 face，从 0 开始；TTF/OTF 使用 0。")
                self.faces[key] = face
                asset_form.addRow("字体 face", face)
        self.asset_status = QLabel()
        self.asset_status.setWordWrap(True)
        self.signature_preview = QLabel("签名预览")
        self.signature_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signature_preview.setMinimumHeight(120)
        self.signature_preview.setStyleSheet(
            "background:#182638; border-radius:10px; color:#dbeafe;"
        )
        health = QPushButton("检查字体与签名")
        health.clicked.connect(self.check_assets)
        asset_form.addRow(health)
        asset_form.addRow(self.asset_status)
        asset_form.addRow(self.signature_preview)
        self.tabs.addTab(assets_page, "本地素材")
        layout_page = QWidget()
        layout_form = QFormLayout(layout_page)
        hint = QLabel(
            "下列尺寸以 6016×4016 基准画布计。程序按实际像素自动缩放整组水印，与照片 DPI 无关。"
        )
        hint.setWordWrap(True)
        layout_form.addRow(hint)
        for key, label, minimum, maximum, suffix in (
            ("font_size_pt", "字号", 1, 300, " pt"),
            ("signature_width", "签名宽度", 1, 3000, " px"),
            ("margin_x", "水平边距", 0, 3000, " px"),
            ("margin_y", "垂直边距", 0, 3000, " px"),
            ("offset_x", "水平偏移", -6000, 6000, " px"),
            ("offset_y", "垂直偏移", -6000, 6000, " px"),
            ("signature_offset_y", "签名组内偏移", -3000, 3000, " px"),
        ):
            control = QDoubleSpinBox()
            control.setRange(minimum, maximum)
            control.setDecimals(2)
            control.setSuffix(suffix)
            self.numbers[key] = control
            layout_form.addRow(label, control)
        self.anchor = QComboBox()
        for label, key in (
            ("右下角", "bottom_right"),
            ("左下角", "bottom_left"),
            ("右上角", "top_right"),
            ("左上角", "top_left"),
        ):
            self.anchor.addItem(label, key)
        layout_form.addRow("位置", self.anchor)
        self.tabs.addTab(layout_page, "大小与位置")
        output_page = QWidget()
        output_form = QFormLayout(output_page)
        self.color = QLineEdit()
        self.color.setPlaceholderText("#FFFFFF")
        output_form.addRow("文字颜色", self.color)
        for key, label in (
            ("latin_opacity", "英文 / 数字不透明度"),
            ("chinese_opacity", "中文不透明度"),
            ("signature_opacity", "签名不透明度"),
        ):
            control = QDoubleSpinBox()
            control.setRange(0, 100)
            control.setSuffix(" %")
            control.setDecimals(1)
            self.numbers[key] = control
            output_form.addRow(label, control)
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        output_form.addRow("JPEG 质量", self.quality)
        self.subsampling = QComboBox()
        for value, label in enumerate(("4:4:4（细节优先）", "4:2:2", "4:2:0（较小文件）")):
            self.subsampling.addItem(label, value)
        output_form.addRow("色度采样", self.subsampling)
        self.allow_create_date = QCheckBox("缺少 DateTimeOriginal 时，允许使用 EXIF CreateDate")
        output_form.addRow(self.allow_create_date)
        output_note = QLabel(
            "导出保留原像素尺寸，颜色转换为 sRGB，并保留拍摄信息与当前 GPS。缺失日期时不会使用今天或文件修改时间。"
        )
        output_note.setWordWrap(True)
        output_form.addRow(output_note)
        self.tabs.addTab(output_page, "颜色与导出")
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#b91c1c;")
        defaults = QPushButton("恢复项目默认")
        defaults.clicked.connect(
            lambda: self._populate(WatermarkSettings(default_local_resources()))
        )
        restore = QPushButton("从备份恢复")
        restore.setEnabled(store.backup.is_file())
        restore.clicked.connect(self.restore_backup)
        save = QPushButton("保存为我的默认")
        save.clicked.connect(self.save_defaults)
        apply = QPushButton("应用")
        apply.setObjectName("primary")
        apply.clicked.connect(self.apply_settings)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        for button in (defaults, restore, save, apply, cancel):
            bottom.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.error_label)
        layout.addLayout(bottom)
        self._populate(settings)

    def _pick_asset(self, key: str) -> None:
        filters = "字体 (*.ttf *.otf *.ttc)" if key != "signature" else "透明签名 (*.png)"
        filename, _ = QFileDialog.getOpenFileName(self, "选择本地素材", "", filters)
        if filename:
            self.assets[key].setText(filename)
            self.check_assets()

    def _populate(self, settings: WatermarkSettings) -> None:
        resources = settings.resources
        for key, edit in self.assets.items():
            edit.setText(str(getattr(resources, key)))
        self.faces["latin_font"].setValue(resources.latin_face)
        self.faces["chinese_font"].setValue(resources.chinese_face)
        defaults = project_default_config("aviation", "TEST", date(2000, 1, 1))
        for key, control in self.numbers.items():
            value = float(cast(float, settings.params.get(key, getattr(defaults, key))))
            control.setValue(value * 100 if key.endswith("opacity") else value)
        self.anchor.setCurrentIndex(
            max(0, self.anchor.findData(settings.params.get("anchor", defaults.anchor)))
        )
        self.color.setText(str(settings.params.get("color_hex", "#FFFFFF")))
        self.quality.setValue(cast(int, settings.params.get("jpeg_quality", 95)))
        self.subsampling.setCurrentIndex(cast(int, settings.params.get("jpeg_subsampling", 0)))
        self.allow_create_date.setChecked(settings.params.get("allow_create_date") is True)
        self.error_label.clear()

    def settings(self) -> WatermarkSettings:
        resources = WatermarkResources(
            Path(self.assets["latin_font"].text()),
            Path(self.assets["chinese_font"].text()),
            Path(self.assets["signature"].text()),
            self.faces["latin_font"].value(),
            self.faces["chinese_font"].value(),
        )
        params: dict[str, Parameter] = {
            key: control.value() / 100 if key.endswith("opacity") else control.value()
            for key, control in self.numbers.items()
        }
        params.update(
            anchor=str(self.anchor.currentData()),
            color_hex=self.color.text().strip(),
            jpeg_quality=self.quality.value(),
            jpeg_subsampling=self.subsampling.currentIndex(),
            allow_create_date=self.allow_create_date.isChecked(),
        )
        color = params["color_hex"]
        if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
            raise ValueError("文字颜色请填写 #RRGGBB")
        if len(bytes.fromhex(color[1:])) != 3:
            raise ValueError("文字颜色请填写 #RRGGBB")
        return WatermarkSettings(resources, params)

    def check_assets(self) -> bool:
        try:
            settings = self.settings()
            resources = settings.resources
            latin = identify_font(resources.latin_font, resources.latin_face)
            names = [f"英文：{latin.family} / {latin.style}"]
            if resources.chinese_font.is_file():
                chinese = identify_font(resources.chinese_font, resources.chinese_face)
                names.append(f"中文：{chinese.family} / {chinese.style}")
            else:
                names.append("中文字体未选择；处理中文风光前需补齐。")
            signature = identify_signature(resources.signature)
            with Image.open(signature.path) as original:
                preview = original.convert("RGBA")
            preview.thumbnail((280, 110))
            rgba = preview.tobytes()
            qimage = QImage(
                rgba,
                preview.width,
                preview.height,
                preview.width * 4,
                QImage.Format.Format_RGBA8888,
            ).copy()
            self.signature_preview.setPixmap(QPixmap.fromImage(qimage))
            names.append(
                f"签名：{signature.size[0]}×{signature.size[1]}；保持源 Alpha 并仅施加一次不透明度。"
            )
            self.asset_status.setText("\n".join(names))
            self.error_label.clear()
            return True
        except (OSError, ValueError) as error:
            self.error_label.setText(f"素材检查未通过：{error}")
            return False

    def apply_settings(self) -> None:
        if self.check_assets():
            self.accept()

    def save_defaults(self) -> None:
        if not self.check_assets():
            return
        try:
            self.store.save(self.settings())
        except (OSError, ValueError) as error:
            self.error_label.setText(f"保存失败：{error}")
            return
        self.accept()

    def restore_backup(self) -> None:
        try:
            self._populate(self.store.restore_backup())
        except (OSError, ValueError) as error:
            self.error_label.setText(f"恢复失败：{error}")
