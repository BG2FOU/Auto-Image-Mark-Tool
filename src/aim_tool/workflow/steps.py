"""Real GPS and JPG watermark components with transactional export."""

from __future__ import annotations

import hashlib
import shutil
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from aim_tool.domain import Artifact, ImageKind, PhotoItem, StepSpec
from aim_tool.domain.dates import resolve_capture_date
from aim_tool.services.exiftool import ExifTool, validate_coordinates
from aim_tool.services.file_state import FileState, file_state
from aim_tool.services.nef_gps import fingerprint_nef
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
        preflight_metadata: dict[Path, dict[str, Any]] | None = None,
        preflight_states: dict[Path, FileState] | None = None,
        cancelled: Event | None = None,
    ) -> None:
        self.tool = tool
        self.allow_nef_after_viewer_check = allow_nef_after_viewer_check
        self.clear_auxiliary_gps = clear_auxiliary_gps
        self._preflight_metadata = preflight_metadata
        self._preflight_states = preflight_states
        self._cancelled = cancelled

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        return input_kind

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        if item.coordinates is None:
            raise ValueError(f"Missing WGS84 coordinates: {item.source.name}")
        validate_coordinates(*item.coordinates)
        if item.source.suffix.lower() == ".nef":
            if not self.allow_nef_after_viewer_check:
                raise ValueError("NEF GPS output needs independent Nikon viewer approval")
            fingerprint_nef(self.tool, item.source)
        metadata = None
        if self._preflight_metadata is not None and item.source.suffix.lower() != ".nef":
            if self._preflight_states is not None:
                self._preflight_states[item.source] = file_state(item.source, self._cancelled)
            metadata = self.tool.metadata(
                item.source, "-ExifIFD:DateTimeOriginal", "-ExifIFD:CreateDate", "-gps:all"
            )
            self._preflight_metadata[item.source] = metadata
        auxiliary = (
            self.tool.has_auxiliary_gps(item.source)
            if metadata is None
            else self.tool.has_auxiliary_gps(item.source, metadata=metadata)
        )
        if auxiliary and not self.clear_auxiliary_gps:
            raise ValueError("Existing auxiliary GPS tags require explicit clearance")

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        if artifact.path != artifact.source:
            raise ValueError("Location step must start from the original source")
        if context.coordinates is None:
            raise ValueError(f"Missing WGS84 coordinates: {artifact.source.name}")
        latitude, longitude = context.coordinates
        before = _sha256(artifact.source)
        raw_before = (
            fingerprint_nef(self.tool, artifact.source) if artifact.kind == ImageKind.NEF else None
        )
        staged = context.scratch / artifact.source.name
        with artifact.source.open("rb") as original, staged.open("xb") as copy:
            shutil.copyfileobj(original, copy, length=1024 * 1024)
        if _sha256(staged) != before:
            raise OSError("Source copy changed before GPS update")
        altitude = context.photo.altitude if context.photo is not None else 0.0
        self.tool.write_gps(staged, latitude, longitude, altitude)
        if raw_before is not None and not fingerprint_nef(self.tool, staged).preserved_from(
            raw_before
        ):
            raise ValueError("RAW, previews or camera metadata changed during GPS update")
        if _sha256(artifact.source) != before:
            raise OSError("Source changed during GPS update")
        updated = dict(artifact.metadata)
        updated["GPSLatitude"] = str(latitude)
        updated["GPSLongitude"] = str(longitude)
        updated["GPSAltitude"] = str(altitude)
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
    source_state: FileState | None = None


class WatermarkPreflightCache:
    """Window-owned, bounded validated summaries; never retain decoded pixel buffers."""

    def __init__(self, limit: int = 256) -> None:
        self.limit = limit
        self._entries: OrderedDict[
            UUID, tuple[FileState, _PreparedWatermark, WatermarkResources]
        ] = OrderedDict()

    def find(
        self,
        photo: PhotoItem,
        spec: StepSpec,
        resources: WatermarkResources,
        state: FileState,
    ) -> _PreparedWatermark | None:
        entry = self._entries.pop(photo.id, None)
        if entry is None:
            return None
        previous, prepared, assets = entry
        if (
            previous != state
            or prepared.photo != photo
            or prepared.spec != spec
            or assets != resources
            or any(_sha256(path) != digest for path, digest in prepared.asset_hashes)
        ):
            return None
        self._entries[photo.id] = entry
        return prepared

    def remember(
        self,
        state: FileState,
        prepared: _PreparedWatermark,
        resources: WatermarkResources,
    ) -> None:
        if self.limit <= 0:
            return
        self._entries[prepared.photo.id] = state, prepared, resources
        self._entries.move_to_end(prepared.photo.id)
        while len(self._entries) > self.limit:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


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
            "digital_enabled": "bool",
            "digital_algorithm": "str",
            "digital_level": "str",
            "digital_key": "str",
        }
    )
    required_parameters: frozenset[str] = frozenset()

    def __init__(
        self,
        tool: ExifTool,
        resources: WatermarkResources,
        *,
        preflight_cache: WatermarkPreflightCache | None = None,
        preflight_metadata: dict[Path, dict[str, Any]] | None = None,
        preflight_states: dict[Path, FileState] | None = None,
        cancelled: Event | None = None,
    ) -> None:
        self.tool = tool
        self.resources = resources
        self._prepared: dict[UUID, _PreparedWatermark] = {}
        self._preflight_cache = preflight_cache
        self._preflight_metadata = preflight_metadata
        self._preflight_states = preflight_states
        self._cancelled = cancelled

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        return ImageKind.JPEG

    def _config(
        self, photo: PhotoItem, spec: StepSpec, *, metadata: Mapping[str, Any] | None = None
    ) -> tuple[WatermarkConfig, str]:
        from aim_tool.services.frequency_watermark import digital_config
        from aim_tool.services.templates import project_default_config
        from aim_tool.services.watermark import Anchor, Category

        category = photo.edits.get("category", "")
        content = photo.edits.get("subject", "")
        if metadata is None:
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
            digital=digital_config(spec.params),
        )
        return config, photo.edits.get("capture_date_source", resolved.source)

    def configuration(self, photo: PhotoItem, spec: StepSpec) -> tuple[WatermarkConfig, str]:
        """Expose the shared date and layout snapshot to an asynchronous preview."""
        return self._config(photo, spec)

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        if item.source.suffix.lower() == ".nef":
            raise ValueError("NEF watermark processing is deferred; select coordinates only")
        from aim_tool.services.images import validate_jpeg
        from aim_tool.services.watermark import render_watermark_region

        state = (
            self._preflight_states.pop(item.source, None)
            if self._preflight_states is not None
            else None
        )
        if state is None and self._preflight_cache:
            state = file_state(item.source, self._cancelled)
        if self._preflight_cache is not None and state is not None:
            cached = self._preflight_cache.find(item, spec, self.resources, state)
            if cached is not None:
                if file_state(item.source, self._cancelled) != state:
                    raise OSError("Source changed during preflight")
                self._prepared[item.id] = cached
                if self._preflight_metadata is not None:
                    self._preflight_metadata.pop(item.source, None)
                return
        metadata = (
            self._preflight_metadata.pop(item.source, None)
            if self._preflight_metadata is not None
            else None
        )
        if metadata is None:
            metadata = self.tool.metadata(
                item.source, "-ExifIFD:DateTimeOriginal", "-ExifIFD:CreateDate", "-GPS:all"
            )
        config, date_source = self._config(item, spec, metadata=metadata)
        self.tool.gps_from_metadata(metadata)
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
        size = validate_jpeg(item.source)
        render_watermark_region(size, config, self.resources)
        if config.digital is not None:
            from aim_tool.services.frequency_watermark import signature_spec

            signature_spec(size, config.digital, self.resources.signature)
        if any(_sha256(path) != digest for path, digest in fingerprints):
            raise ValueError("Watermark asset changed during preflight")
        prepared = _PreparedWatermark(item, spec, config, date_source, fingerprints, state)
        if self._preflight_cache is not None and state is not None:
            if self._cancelled is not None and self._cancelled.is_set():
                raise InterruptedError("检查已取消")
            if file_state(item.source, self._cancelled) != state:
                raise OSError("Source changed during preflight")
            self._preflight_cache.remember(state, prepared, self.resources)
        self._prepared[item.id] = prepared

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        from aim_tool.services.images import _encode_watermark_jpeg
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
        if prepared.source_state is not None:
            current = file_state(artifact.source, context.cancelled)
            if current != prepared.source_state:
                raise OSError("Source changed after preflight")
            original_hash = current.digest
        else:
            original_hash = _sha256(artifact.source)
        authority_hash = _sha256(artifact.path)
        target = context.scratch / "watermark" / "rendered.jpg"
        warnings = _encode_watermark_jpeg(
            artifact.path,
            target,
            prepared.config,
            self.resources,
            quality=cast(int, spec.params.get("jpeg_quality", 95)),
            subsampling=cast(int, spec.params.get("jpeg_subsampling", 0)),
            cancelled=context.cancelled,
        )
        for warning in warnings:
            context.warning(warning)
        if context.cancelled.is_set():
            raise InterruptedError("水印处理已取消")
        preserve_watermark_metadata(self.tool, artifact.path, target)
        if prepared.config.digital is not None:
            from aim_tool.services.frequency_watermark import verify_signature

            verify_signature(
                target,
                prepared.config.digital,
                self.resources.signature,
                cancelled=context.cancelled,
            )
        if _sha256(artifact.source) != original_hash or _sha256(artifact.path) != authority_hash:
            raise OSError("Source or current artifact changed during watermark export")
        if any(_sha256(path) != digest for path, digest in prepared.asset_hashes):
            raise ValueError("Watermark asset changed during rendering")
        context.progress(
            f"Watermark and metadata readback passed; date source: {prepared.date_source}"
        )
        return Artifact(artifact.source, target, ImageKind.JPEG, artifact.metadata)
