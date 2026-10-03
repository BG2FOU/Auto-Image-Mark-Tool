"""Qt signal bridge for preflighted GPS and watermark batch jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from aim_tool.domain import BatchJob, PhotoItem, StepSpec
from aim_tool.services.exiftool import ExifTool
from aim_tool.services.storage import WatermarkSettings
from aim_tool.workflow.engine import ExecutionPlan, build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry
from aim_tool.workflow.steps import ExportStep, LocationStep, WatermarkStep


class BatchWorker(QThread):
    progress = Signal(str, str)
    completed = Signal(object)

    def __init__(self, plan: ExecutionPlan, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.cancelled = Event()

    def run(self) -> None:
        results = run_plan(
            self.plan,
            cancelled=self.cancelled,
            progress=lambda photo, message: self.progress.emit(str(photo.id), message),
        )
        self.completed.emit(results)


class MetadataWorker(QThread):
    ready = Signal(str, object)
    error = Signal(str)

    def __init__(self, photos: tuple[PhotoItem, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.photos = photos
        self.cancelled = Event()

    def run(self) -> None:
        try:
            tool = ExifTool(timeout=30)
            for photo in self.photos:
                if self.cancelled.is_set():
                    break
                try:
                    metadata = tool.metadata(
                        photo.source,
                        "-ExifIFD:DateTimeOriginal",
                        "-ExifIFD:CreateDate",
                        "-File:ImageWidth",
                        "-File:ImageHeight",
                        "-IFD0:Orientation",
                    )
                    self.ready.emit(
                        str(photo.id), {key: str(value) for key, value in metadata.items()}
                    )
                except Exception as error:  # noqa: BLE001 - report worker failures through Qt signals
                    self.error.emit(f"{photo.source.name}：元数据读取失败：{error}")
        except Exception as error:  # noqa: BLE001 - report worker failures through Qt signals
            self.error.emit(f"ExifTool 不可用：{error}")


class PreflightWorker(QThread):
    ready = Signal(object)
    error = Signal(str)
    item_error = Signal(str, str)

    def __init__(
        self,
        job: BatchJob,
        settings: WatermarkSettings,
        parent: QWidget | None = None,
        *,
        clear_auxiliary_gps: bool = False,
        allow_nef_after_viewer_check: bool = False,
    ) -> None:
        super().__init__(parent)
        self.clear_auxiliary_gps = clear_auxiliary_gps
        self.allow_nef_after_viewer_check = allow_nef_after_viewer_check
        self.job = job
        self.settings = settings
        self.cancelled = Event()

    def run(self) -> None:
        try:
            tool = ExifTool(timeout=30)
            registry = StepRegistry()
            registry.register(
                LocationStep(
                    tool,
                    clear_auxiliary_gps=self.clear_auxiliary_gps,
                    allow_nef_after_viewer_check=self.allow_nef_after_viewer_check,
                )
            )
            registry.register(WatermarkStep(tool, self.settings.resources))
            registry.register(ExportStep())
            plan = build_plan(self.job, registry, cancelled=self.cancelled)
            if not self.cancelled.is_set():
                self.ready.emit(plan)
        except Exception as error:  # noqa: BLE001 - report worker failures through Qt signals
            if not self.cancelled.is_set():
                self.error.emit("\n".join([str(error), *getattr(error, "__notes__", ())]))
                photo_id = getattr(error, "photo_id", None)
                if photo_id is not None:
                    self.item_error.emit(str(photo_id), str(error))


@dataclass(frozen=True)
class PreviewRequest:
    generation: int
    photo: PhotoItem
    settings: WatermarkSettings | None


@dataclass(frozen=True)
class PreviewResult:
    generation: int
    photo_id: str
    image: QImage
    detail: QImage
    size: tuple[int, int]
    bounds: tuple[int, int, int, int] | None
    caption: str
    warnings: tuple[str, ...]


def _qimage(image: Image.Image) -> QImage:
    rgb = image.convert("RGB")
    return QImage(
        rgb.tobytes(), rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888
    ).copy()


class PreviewWorker(QThread):
    ready = Signal(object)
    error = Signal(int, str)

    def __init__(self, request: PreviewRequest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.request = request
        self.cancelled = Event()

    def run(self) -> None:
        from aim_tool.services.images import prepare_jpeg
        from aim_tool.services.watermark import render_watermark_layer, watermark_scale

        request = self.request
        try:
            prepared = prepare_jpeg(request.photo.source)
            size = prepared.pixels.size
            bounds = None
            caption = f"{size[0]} × {size[1]} px"
            pixels = prepared.pixels
            if request.settings is not None:
                tool = ExifTool(timeout=30)
                step = WatermarkStep(tool, request.settings.resources)
                config, date_source = step.configuration(
                    request.photo, StepSpec("watermark", params=request.settings.params)
                )
                if self.cancelled.is_set():
                    return
                overlay = render_watermark_layer(size, config, request.settings.resources)
                bounds = overlay.getchannel("A").getbbox()
                pixels = Image.alpha_composite(pixels.convert("RGBA"), overlay).convert("RGB")
                scale = watermark_scale(size, config)
                date_source = {
                    "manual": "手动",
                    "table": "表格",
                    "EXIF DateTimeOriginal": "EXIF 拍摄时间",
                    "EXIF CreateDate": "EXIF 创建时间",
                }.get(date_source, date_source)
                caption += f"\n字号 {max(1, round(config.font_size_pt * config.base_ppi / 72 * scale))} px · 签名 {max(1, round(config.signature_width * scale))} px · {config.taken_on:%Y/%m/%d}（{date_source}）"
            if self.cancelled.is_set():
                return
            if bounds is not None:
                left, top, right, bottom = bounds
                detail = pixels.crop(
                    (
                        max(0, left - 12),
                        max(0, top - 12),
                        min(size[0], right + 12),
                        min(size[1], bottom + 12),
                    )
                )
            else:
                detail = pixels.crop((0, 0, min(size[0], 800), min(size[1], 600)))
            pixels.thumbnail((1400, 1000), Image.Resampling.LANCZOS)
            result = PreviewResult(
                request.generation,
                str(request.photo.id),
                _qimage(pixels),
                _qimage(detail),
                size,
                bounds,
                caption,
                prepared.warnings,
            )
            if not self.cancelled.is_set():
                self.ready.emit(result)
        except Exception as error:  # noqa: BLE001 - report worker failures through Qt signals
            if not self.cancelled.is_set():
                self.error.emit(request.generation, str(error))


class TableImportWorker(QThread):
    ready = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        photos: tuple[PhotoItem, ...],
        *,
        path: Path | None,
        text: str,
        encoding: str,
        sheet: str | None,
        mapping: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.photos, self.path, self.text = photos, path, text
        self.encoding, self.sheet, self.mapping = encoding, sheet, dict(mapping)

    def run(self) -> None:
        from aim_tool.services.table_import import preview_import, read_pasted_tsv, read_table

        try:
            rows = (
                read_table(
                    self.path, encoding=self.encoding, sheet=self.sheet, column_mapping=self.mapping
                )
                if self.path is not None
                else read_pasted_tsv(self.text, column_mapping=self.mapping)
            )
            self.ready.emit(preview_import(rows, self.photos))
        except Exception as error:  # noqa: BLE001 - surface parsing errors in the dialog
            self.error.emit(str(error))
