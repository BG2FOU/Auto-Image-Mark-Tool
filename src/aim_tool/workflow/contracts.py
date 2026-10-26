"""Narrow contracts for reviewed, in-process workflow components."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Literal, Protocol

from aim_tool.domain import Artifact, ImageKind, PhotoItem, StepSpec
from aim_tool.services.file_state import FileState

type PreflightMode = Literal["quick", "full"]


@dataclass(frozen=True)
class StepContext:
    target: Path
    cancelled: Event
    progress: Callable[[str], None]
    scratch: Path
    coordinates: tuple[float, float] | None
    photo: PhotoItem | None = None
    warning: Callable[[str], None] = lambda message: None
    source_state: FileState | None = None
    source_metadata: dict[str, Any] | None = None
    component_ids: frozenset[str] = frozenset()


type ParameterType = Literal["str", "int", "float", "bool", "null"]


class Step(Protocol):
    id: str
    version: int
    source_kinds: frozenset[ImageKind]
    accepts: frozenset[ImageKind]
    parameter_schema: Mapping[str, ParameterType]
    required_parameters: frozenset[str]

    def output_kind(self, input_kind: ImageKind) -> ImageKind: ...

    def validate(self, item: PhotoItem, spec: StepSpec) -> None: ...

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact: ...
