"""Real GPS and JPG watermark components with transactional export."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, cast
from uuid import UUID

from aim_tool.domain import Artifact, ImageKind, PhotoItem, StepSpec
from aim_tool.domain.dates import resolve_capture_date
from aim_tool.services.exiftool import ExifTool, validate_coordinates
from aim_tool.services.output import commit_no_overwrite
from aim_tool.workflow.contracts import ParameterType, StepContext

if TYPE_CHECKING:
    from aim_tool.services.watermark import WatermarkConfig, WatermarkResources


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class LocationStep:
    id = "location"
    version = 1
    source_kinds = frozenset({ImageKind.JPEG, ImageKind.NEF})
    accepts = source_kinds
    parameter_schema: Mapping[str, ParameterType] = MappingProxyType({})
    required_parameters: frozenset[str] = frozenset()

    def __init__(
        self,
        tool: ExifTool,
        *,
        allow_nef_after_viewer_check: bool = False,
        clear_auxiliary_gps: bool = False,
    ) -> None:
        self.tool = tool
        self.allow_nef_after_viewer_check = allow_nef_after_viewer_check
        self.clear_auxiliary_gps = clear_auxiliary_gps

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        return input_kind

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        if item.coordinates is None:
            raise ValueError(f"Missing WGS84 coordinates: {item.source.name}")
        validate_coordinates(*item.coordinates)
        if item.source.suffix.lower() == ".nef" and not self.allow_nef_after_viewer_check:
            raise ValueError("NEF GPS output needs independent Nikon viewer approval")
        if self.tool.has_auxiliary_gps(item.source) and not self.clear_auxiliary_gps:
            raise ValueError("Existing auxiliary GPS tags require explicit clearance")

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        if artifact.path != artifact.source:
            raise ValueError("Location step must start from the original source")
        if context.coordinates is None:
            raise ValueError(f"Missing WGS84 coordinates: {artifact.source.name}")
        latitude, longitude = context.coordinates
        before = _sha256(artifact.source)
        staged = context.scratch / artifact.source.name
        with artifact.source.open("rb") as original, staged.open("xb") as copy:
            shutil.copyfileobj(original, copy, length=1024 * 1024)
        if _sha256(staged) != before:
            raise OSError("Source copy changed before GPS update")
        self.tool.write_gps(staged, latitude, longitude)
        if _sha256(artifact.source) != before:
            raise OSError("Source changed during GPS update")
        updated = dict(artifact.metadata)
        updated["GPSLatitude"] = str(latitude)
        updated["GPSLongitude"] = str(longitude)
        context.progress("GPS readback passed")
        return Artifact(artifact.source, staged, artifact.kind, updated)


class ExportStep:
    id = "export"
    version = 1
    source_kinds = frozenset({ImageKind.JPEG, ImageKind.NEF})
    accepts = source_kinds
    parameter_schema: Mapping[str, ParameterType] = MappingProxyType({})
    required_parameters: frozenset[str] = frozenset()

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        return ImageKind.EXPORTED

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        return None

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        staged = artifact.path.resolve()
        if not staged.is_relative_to(context.scratch.resolve()) or not staged.is_file():
            raise ValueError("Export requires a staged file from this job")
        commit_no_overwrite(staged, context.target)
        context.progress("Committed output without overwrite")
        return Artifact(artifact.source, context.target, ImageKind.EXPORTED, artifact.metadata)


class RawDevelopStep:
    """Explicitly block deferred NEF image processing without importing rawpy."""

    id = "raw_develop"
    version = 1
    source_kinds = frozenset({ImageKind.NEF})
    accepts = source_kinds
    parameter_schema: Mapping[str, ParameterType] = MappingProxyType({})
    required_parameters: frozenset[str] = frozenset()

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        return ImageKind.RASTER

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        raise ValueError("NEF watermark processing is deferred; use JPG/JPEG")

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        raise ValueError("NEF watermark processing is deferred; use JPG/JPEG")


@dataclass(frozen=True)
class _PreparedWatermark:
    photo: PhotoItem
    spec: StepSpec
    config: WatermarkConfig
    date_source: str
    asset_hashes: tuple[tuple[Path, str], ...]


class WatermarkStep:
    id = "watermark"
    version = 1
    source_kinds = frozenset({ImageKind.JPEG, ImageKind.NEF})
    accepts = frozenset({ImageKind.JPEG})
    parameter_schema: Mapping[str, ParameterType] = MappingProxyType(
        {
            "font_size_pt": "float",
            "signature_width": "float",
            "margin_x": "float",
            "margin_y": "float",
            "offset_x": "float",
            "offset_y": "float",
            "signature_offset_y": "float",
            "anchor": "str",
            "color_hex": "str",
            "latin_opacity": "float",
            "chinese_opacity": "float",
            "signature_opacity": "float",
            "allow_create_date": "bool",
            "jpeg_quality": "int",
            "jpeg_subsampling": "int",
        }
    )
    required_parameters: frozenset[str] = frozenset()

    def __init__(self, tool: ExifTool, resources: WatermarkResources) -> None:
        self.tool = tool
        self.resources = resources
        self._prepared: dict[UUID, _PreparedWatermark] = {}

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        return ImageKind.JPEG

    def _config(self, photo: PhotoItem, spec: StepSpec) -> tuple[WatermarkConfig, str]:
        from aim_tool.services.templates import project_default_config
        from aim_tool.services.watermark import Anchor, Category

        category = photo.edits.get("category", "")
        content = photo.edits.get("subject", "")
        metadata = self.tool.metadata(
            photo.source, "-ExifIFD:DateTimeOriginal", "-ExifIFD:CreateDate"
        )
        resolved = resolve_capture_date(
            manual=photo.taken_on,
            exif_datetime_original=metadata.get("ExifIFD:DateTimeOriginal"),
            exif_create_date=metadata.get("ExifIFD:CreateDate"),
            allow_create_date=spec.params.get("allow_create_date") is True,
        )
        config = project_default_config(cast(Category, category), content, resolved.day)
        color = spec.params.get("color_hex", "#FFFFFF")
        if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
            raise ValueError("Watermark color must be #RRGGBB")
        try:
            channels = bytes.fromhex(color[1:])
            if len(channels) != 3:
                raise ValueError("Invalid color")
        except ValueError as error:
            raise ValueError("Watermark color must be #RRGGBB") from error

        def value(name: str, default: float) -> float:
            parameter = spec.params.get(name, default)
            if type(parameter) not in {int, float}:
                raise ValueError(f"Invalid watermark parameter: {name}")
            return float(parameter)  # type: ignore[arg-type]

        config = replace(
            config,
            font_size_pt=value("font_size_pt", config.font_size_pt),
            signature_width=value("signature_width", config.signature_width),
            margin_x=value("margin_x", config.margin_x),
            margin_y=value("margin_y", config.margin_y),
            offset_x=value("offset_x", config.offset_x),
            offset_y=value("offset_y", config.offset_y),
            signature_offset_y=value("signature_offset_y", config.signature_offset_y),
            anchor=cast(Anchor, spec.params.get("anchor", config.anchor)),
            color=(channels[0], channels[1], channels[2]),
            latin_opacity=value("latin_opacity", config.latin_opacity),
            chinese_opacity=value("chinese_opacity", config.chinese_opacity),
            signature_opacity=value("signature_opacity", config.signature_opacity),
        )
        return config, photo.edits.get("date_source", resolved.source)

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        from aim_tool.services.images import prepare_jpeg
        from aim_tool.services.watermark import render_watermark_layer

        config, date_source = self._config(item, spec)
        self.tool.read_gps(item.source)
        quality = spec.params.get("jpeg_quality", 95)
        subsampling = spec.params.get("jpeg_subsampling", 0)
        if type(quality) is not int or not 1 <= quality <= 100:
            raise ValueError("JPEG quality must be an integer from 1 to 100")
        if type(subsampling) is not int or subsampling not in {0, 1, 2}:
            raise ValueError("JPEG subsampling must be 0, 1 or 2")
        paths = [self.resources.latin_font, self.resources.signature]
        if config.category == "landscape" and any(
            not character.isascii() for character in config.content
        ):
            paths.append(self.resources.chinese_font)
        fingerprints = tuple((path, _sha256(path)) for path in paths)
        prepared = prepare_jpeg(item.source)
        render_watermark_layer(prepared.pixels.size, config, self.resources)
        if any(_sha256(path) != digest for path, digest in fingerprints):
            raise ValueError("Watermark asset changed during preflight")
        self._prepared[item.id] = _PreparedWatermark(item, spec, config, date_source, fingerprints)

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        from aim_tool.services.images import export_watermark_preview
        from aim_tool.services.metadata import preserve_watermark_metadata

        if context.photo is None:
            raise ValueError("Watermark step requires its preflight photo snapshot")
        prepared = self._prepared.get(context.photo.id)
        if prepared is None or prepared.photo != context.photo or prepared.spec != spec:
            raise ValueError("Watermark configuration differs from preflight")
        if artifact.path != artifact.source and not artifact.path.resolve().is_relative_to(
            context.scratch.resolve()
        ):
            raise ValueError("Watermark input must be the original or this job's staged artifact")
        for path, digest in prepared.asset_hashes:
            if _sha256(path) != digest:
                raise ValueError("Watermark asset changed after preflight")
        original_hash = _sha256(artifact.source)
        authority_hash = _sha256(artifact.path)
        target = context.scratch / "watermark" / "rendered.jpg"
        warnings = export_watermark_preview(
            artifact.path,
            target,
            prepared.config,
            self.resources,
            quality=cast(int, spec.params.get("jpeg_quality", 95)),
            subsampling=cast(int, spec.params.get("jpeg_subsampling", 0)),
        )
        for warning in warnings:
            context.warning(warning)
        preserve_watermark_metadata(self.tool, artifact.path, target)
        if _sha256(artifact.source) != original_hash or _sha256(artifact.path) != authority_hash:
            raise OSError("Source or current artifact changed during watermark export")
        if any(_sha256(path) != digest for path, digest in prepared.asset_hashes):
            raise ValueError("Watermark asset changed during rendering")
        context.progress(
            f"Watermark and metadata readback passed; date source: {prepared.date_source}"
        )
        return Artifact(artifact.source, target, ImageKind.JPEG, artifact.metadata)
