"""Typed, GUI-independent data exchanged by the workflow engine."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from uuid import UUID, uuid4

from aim_tool.domain.validation import validate_altitude


class ImageKind(StrEnum):
    JPEG = "jpeg"
    NEF = "nef"
    RASTER = "raster"
    EXPORTED = "exported"


class ItemStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


type Parameter = str | int | float | bool | None


@dataclass(frozen=True)
class StepSpec:
    component_id: str
    version: int = 1
    enabled: bool = True
    params: Mapping[str, Parameter] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@dataclass(frozen=True)
class WorkflowSpec:
    steps: tuple[StepSpec, ...]
    schema_version: int = 1


@dataclass(frozen=True)
class PhotoItem:
    source: Path
    import_root: Path
    id: UUID = field(default_factory=uuid4)
    metadata: Mapping[str, str] = field(default_factory=dict)
    edits: Mapping[str, str] = field(default_factory=dict)
    taken_on: date | None = None
    coordinates: tuple[float, float] | None = None
    altitude: float = 0.0

    def __post_init__(self) -> None:
        validate_altitude(self.altitude)
        object.__setattr__(self, "source", self.source.resolve())
        object.__setattr__(self, "import_root", self.import_root.resolve())
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "edits", MappingProxyType(dict(self.edits)))


@dataclass(frozen=True)
class LocationPreset:
    name: str
    latitude: float
    longitude: float
    id: UUID = field(default_factory=uuid4)
    coordinate_system: str = "WGS84"
    schema_version: int = 1
    altitude: float = 0.0

    def __post_init__(self) -> None:
        validate_altitude(self.altitude)
        if (
            not self.name
            or self.coordinate_system != "WGS84"
            or self.schema_version != 1
            or not math.isfinite(self.latitude)
            or not math.isfinite(self.longitude)
            or not -90 <= self.latitude <= 90
            or not -180 <= self.longitude <= 180
        ):
            raise ValueError("Invalid WGS84 location preset")


@dataclass(frozen=True)
class WatermarkTemplate:
    category: str
    content_font_role: str
    latin_font_role: str = "latin_bold"
    separator: str = "|"
    font_size_pt: float = 36.0
    base_width: int = 6016
    base_height: int = 4016
    color: tuple[int, int, int] = (255, 255, 255)
    text_opacity: float = 0.5
    signature_opacity: float = 0.5
    signature_width: int = 300
    margin: int = 25
    anchor: str = "bottom_right"


@dataclass(frozen=True)
class Artifact:
    source: Path
    path: Path
    kind: ImageKind
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class BatchJob:
    photos: tuple[PhotoItem, ...]
    workflow: WorkflowSpec
    output_root: Path


@dataclass(frozen=True)
class ItemResult:
    photo_id: UUID
    status: ItemStatus
    output: Path | None = None
    current_step: str | None = None
    error: str | None = None
    warnings: tuple[str, ...] = ()
