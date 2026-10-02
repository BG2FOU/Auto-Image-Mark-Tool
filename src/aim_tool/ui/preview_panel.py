"""Coalesced asynchronous previews with full-resolution watermark detail and dragging."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from aim_tool.domain import PhotoItem
from aim_tool.services.storage import WatermarkSettings
from aim_tool.ui.workers import PreviewRequest, PreviewResult, PreviewWorker


class PreviewCanvas(QWidget):
    moved = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 240)
        self.image = QImage()
        self.original_size = (1, 1)
        self.bounds: tuple[int, int, int, int] | None = None
        self.background = "dark"
        self._start: QPointF | None = None
        self._delta = QPointF()
        self.setMouseTracking(True)

    def image_rect(self) -> QRectF:
        if self.image.isNull():
            return QRectF()
        scale = min(
            (self.width() - 24) / self.image.width(), (self.height() - 24) / self.image.height()
        )
        width, height = self.image.width() * scale, self.image.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def watermark_rect(self) -> QRectF:
        if self.bounds is None:
            return QRectF()
        rect = self.image_rect()
        width, height = self.original_size
        left, top, right, bottom = self.bounds
        return QRectF(
            rect.left() + left / width * rect.width(),
            rect.top() + top / height * rect.height(),
            (right - left) / width * rect.width(),
            (bottom - top) / height * rect.height(),
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#172337" if self.background == "dark" else "#e8edf3"))
        if self.background == "checker":
            for y in range(0, self.height(), 18):
                for x in range(0, self.width(), 18):
                    painter.fillRect(
                        x, y, 18, 18, QColor("#d1d8e2" if (x // 18 + y // 18) % 2 else "#edf1f6")
                    )
        if not self.image.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(self.image_rect(), self.image)
            if self._start is not None:
                painter.setPen(QPen(QColor("#38bdf8"), 2, Qt.PenStyle.DashLine))
                painter.drawRect(self.watermark_rect().translated(self._delta))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.watermark_rect().adjusted(
            -3, -3, 3, 3
        ).contains(event.position()):
            self._start = event.position()
            self._delta = QPointF()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            self._delta = event.position() - self._start
            self.update()
        else:
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.watermark_rect().contains(event.position())
                else Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._start is not None and event.button() == Qt.MouseButton.LeftButton:
            delta = event.position() - self._start
            rect = self.image_rect()
            self._start = None
            self._delta = QPointF()
            self.update()
            if rect.width() > 0 and rect.height() > 0:
                self.moved.emit(
                    delta.x() * self.original_size[0] / rect.width(),
                    delta.y() * self.original_size[1] / rect.height(),
                )


class PreviewPanel(QWidget):
    moved = Signal(float, float)
    idle = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.generation = 0
        self._worker: PreviewWorker | None = None
        self._pending: PreviewRequest | None = None
        self._closed = False
        self.last_result: PreviewResult | None = None
        heading = QLabel("画面预览")
        heading.setObjectName("sectionTitle")
        self.zoom = QComboBox()
        self.zoom.addItems(("适应画面", "100% 水印局部"))
        self.background = QComboBox()
        for label, key in (("深色背景", "dark"), ("浅色背景", "light"), ("棋盘背景", "checker")):
            self.background.addItem(label, key)
        controls = QHBoxLayout()
        controls.addWidget(self.zoom)
        controls.addWidget(self.background)
        self.canvas = PreviewCanvas()
        self.canvas.moved.connect(self.moved)
        self.detail = QLabel()
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidget(self.detail)
        scroll.setWidgetResizable(False)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.canvas)
        self.stack.addWidget(scroll)
        self.caption = QLabel("选择一张 JPG 查看预览\n填写内容后可查看水印，点击开始才会导出。")
        self.caption.setWordWrap(True)
        self.caption.setObjectName("muted")
        self.hint = QLabel("在适应画面预览中拖动水印，可调整位置。")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(heading)
        layout.addLayout(controls)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.caption)
        layout.addWidget(self.hint)
        self.zoom.currentIndexChanged.connect(self.stack.setCurrentIndex)
        self.background.currentIndexChanged.connect(self._background_changed)

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def _background_changed(self) -> None:
        self.canvas.background = str(self.background.currentData())
        self.canvas.update()

    def invalidate(self, message: str) -> None:
        self.generation += 1
        self._pending = None
        if self._worker is not None:
            self._worker.cancelled.set()
        self.canvas.image = QImage()
        self.canvas.bounds = None
        self.canvas.update()
        self.detail.clear()
        self.last_result = None
        self.caption.setText(message)

    def request(self, photo: PhotoItem, settings: WatermarkSettings | None) -> None:
        if self._closed:
            return
        self.generation += 1
        self._pending = PreviewRequest(self.generation, photo, settings)
        self.canvas.bounds = None
        self.caption.setText(f"正在生成 {photo.source.name} 的预览…")
        if self._worker is not None:
            self._worker.cancelled.set()
        else:
            self._start_pending()

    def _start_pending(self) -> None:
        if self._pending is None or self._closed:
            return
        request, self._pending = self._pending, None
        worker = PreviewWorker(request, self)
        self._worker = worker
        worker.ready.connect(self.accept_result)
        worker.error.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def accept_result(self, result: PreviewResult) -> None:
        if result.generation != self.generation or self._closed:
            return
        self.last_result = result
        self.canvas.image, self.canvas.original_size, self.canvas.bounds = (
            result.image,
            result.size,
            result.bounds,
        )
        self.canvas.update()
        self.detail.setPixmap(QPixmap.fromImage(result.detail))
        self.detail.adjustSize()
        self.caption.setText(
            result.caption + ("\n" + "\n".join(result.warnings) if result.warnings else "")
        )

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.invalidate(f"预览未通过：{message}")

    def _finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._start_pending()
        if self._worker is None:
            self.idle.emit()

    def shutdown(self) -> None:
        self._closed = True
        self._pending = None
        if self._worker is not None:
            self._worker.cancelled.set()
