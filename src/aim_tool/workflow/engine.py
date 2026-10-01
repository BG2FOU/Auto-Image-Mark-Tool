"""Whole-batch preflight and serial, failure-isolated execution."""

from __future__ import annotations

import math
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from aim_tool.domain import (
    Artifact,
    BatchJob,
    ImageKind,
    ItemResult,
    ItemStatus,
    PhotoItem,
    StepSpec,
)
from aim_tool.services.output import OutputError, output_path, require_distinct_targets
from aim_tool.workflow.contracts import Step, StepContext
from aim_tool.workflow.registry import StepRegistry, WorkflowError


@dataclass(frozen=True)
class PlannedStep:
    spec: StepSpec
    implementation: Step
    expected_kind: ImageKind


@dataclass(frozen=True)
class PlannedItem:
    photo: PhotoItem
    target: Path
    source_kind: ImageKind
    source_size: int
    source_mtime_ns: int
    steps: tuple[PlannedStep, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    items: tuple[PlannedItem, ...]


def _source_kind(photo: PhotoItem) -> ImageKind:
    if photo.source.suffix.lower() in {".jpg", ".jpeg"}:
        return ImageKind.JPEG
    if photo.source.suffix.lower() == ".nef":
        return ImageKind.NEF
    raise WorkflowError(f"Unsupported input: {photo.source.name}")


def _validate_order(job: BatchJob, registry: StepRegistry) -> tuple[StepSpec, ...]:
    workflow = job.workflow
    if workflow.schema_version != 1:
        raise WorkflowError(f"Unsupported workflow schema: {workflow.schema_version}")
    if not job.photos:
        raise WorkflowError("Batch has no photos")
    ids = [spec.component_id for spec in workflow.steps]
    if len(set(ids)) != len(ids):
        raise WorkflowError("Duplicate component in workflow")
    for spec in workflow.steps:
        implementation = registry.get(spec.component_id)
        if spec.version != implementation.version:
            raise WorkflowError(f"Unsupported component version: {spec.component_id}")
    enabled = tuple(spec for spec in workflow.steps if spec.enabled)
    enabled_ids = [spec.component_id for spec in enabled]
    if not enabled_ids or enabled_ids.count("export") != 1 or enabled_ids[-1] != "export":
        raise WorkflowError("Export must be the final enabled component")
    for earlier, later in (
        ("location", "raw_develop"),
        ("location", "watermark"),
        ("raw_develop", "watermark"),
    ):
        if (
            earlier in enabled_ids
            and later in enabled_ids
            and enabled_ids.index(earlier) > enabled_ids.index(later)
        ):
            raise WorkflowError(f"{earlier} must precede {later}")
    return enabled


def _validate_parameters(spec: StepSpec, implementation: Step) -> None:
    missing = implementation.required_parameters - spec.params.keys()
    if missing:
        raise WorkflowError(f"Missing {spec.component_id} parameters: {sorted(missing)}")
    for name, value in spec.params.items():
        expected = implementation.parameter_schema.get(name)
        if expected is None:
            raise WorkflowError(f"Unknown {spec.component_id} parameter: {name}")
        valid = (
            expected == "str"
            and type(value) is str
            or expected == "int"
            and type(value) is int
            or expected == "float"
            and type(value) in {int, float}
            or expected == "bool"
            and type(value) is bool
            or expected == "null"
            and value is None
        )
        if not valid or isinstance(value, float) and not math.isfinite(value):
            raise WorkflowError(f"Invalid {spec.component_id} parameter: {name}")


def build_plan(job: BatchJob, registry: StepRegistry) -> ExecutionPlan:
    """Reject every unsafe item before any step can execute."""
    enabled = _validate_order(job, registry)
    planned: list[PlannedItem] = []
    seen_ids: set[object] = set()
    for photo in job.photos:
        if photo.id in seen_ids:
            raise WorkflowError(f"Duplicate photo ID: {photo.id}")
        seen_ids.add(photo.id)
        try:
            target = output_path(photo, job.workflow, job.output_root)
        except OutputError as error:
            raise WorkflowError(str(error)) from error
        source_kind = _source_kind(photo)
        kind = source_kind
        steps: list[PlannedStep] = []
        for spec in enabled:
            implementation = registry.get(spec.component_id)
            _validate_parameters(spec, implementation)
            if source_kind not in implementation.source_kinds:
                continue
            if kind not in implementation.accepts:
                raise WorkflowError(
                    f"{spec.component_id} cannot consume {kind.value} for {photo.source.name}"
                )
            implementation.validate(photo, spec)
            kind = implementation.output_kind(kind)
            steps.append(PlannedStep(spec, implementation, kind))
        if kind != ImageKind.EXPORTED:
            raise WorkflowError(f"Workflow does not export {photo.source.name}")
        source_stat = photo.source.stat()
        planned.append(
            PlannedItem(
                photo,
                target,
                source_kind,
                source_stat.st_size,
                source_stat.st_mtime_ns,
                tuple(steps),
            )
        )
    try:
        require_distinct_targets(tuple(item.target for item in planned))
    except OutputError as error:
        raise WorkflowError(str(error)) from error
    return ExecutionPlan(tuple(planned))


def run_plan(
    plan: ExecutionPlan,
    cancelled: Event | None = None,
    progress: Callable[[PhotoItem, str], None] | None = None,
) -> tuple[ItemResult, ...]:
    """Run only an already validated plan; one failed photo does not stop others."""
    signal = cancelled or Event()
    results: list[ItemResult] = []
    for item in plan.items:
        photo = item.photo
        if signal.is_set():
            results.append(ItemResult(photo.id, ItemStatus.CANCELLED))
            continue
        current_step: str | None = None
        try:
            source_stat = photo.source.stat()
            if (
                source_stat.st_size != item.source_size
                or source_stat.st_mtime_ns != item.source_mtime_ns
            ):
                raise WorkflowError("Source changed after preflight")
            item.target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".aim-gps-", dir=item.target.parent) as name:
                scratch = Path(name)
                artifact = Artifact(photo.source, photo.source, item.source_kind, photo.metadata)
                for planned_step in item.steps:
                    if signal.is_set():
                        break
                    current_step = planned_step.spec.component_id

                    def report(message: str, current_photo: PhotoItem = photo) -> None:
                        if progress is not None:
                            progress(current_photo, message)

                    context = StepContext(item.target, signal, report, scratch, photo.coordinates)
                    artifact = planned_step.implementation.execute(
                        artifact, planned_step.spec, context
                    )
                    if (
                        artifact.source != photo.source
                        or artifact.kind != planned_step.expected_kind
                    ):
                        raise WorkflowError(f"{current_step} returned an invalid artifact")
                if signal.is_set() and artifact.kind != ImageKind.EXPORTED:
                    results.append(
                        ItemResult(photo.id, ItemStatus.CANCELLED, current_step=current_step)
                    )
                elif artifact.kind != ImageKind.EXPORTED or artifact.path != item.target:
                    results.append(
                        ItemResult(
                            photo.id,
                            ItemStatus.FAILED,
                            current_step=current_step,
                            error="Export component did not return the planned target",
                        )
                    )
                else:
                    results.append(ItemResult(photo.id, ItemStatus.SUCCESS, output=item.target))
        except Exception as error:  # noqa: BLE001 - isolate a failed component to one item
            results.append(
                ItemResult(photo.id, ItemStatus.FAILED, current_step=current_step, error=str(error))
            )
    return tuple(results)
