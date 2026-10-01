"""Real GPS-only components; watermark and RAW development are added later."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from aim_tool.domain import Artifact, ImageKind, PhotoItem, StepSpec
from aim_tool.services.exiftool import ExifTool, validate_coordinates
from aim_tool.services.output import commit_no_overwrite
from aim_tool.workflow.contracts import ParameterType, StepContext


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
