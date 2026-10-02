"""S2 preflight and fake-step execution; no real image is modified."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

import pytest

from aim_tool.domain import (
    Artifact,
    BatchJob,
    ImageKind,
    ItemStatus,
    PhotoItem,
    StepSpec,
    WorkflowSpec,
)
from aim_tool.workflow.contracts import ParameterType, StepContext
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, WorkflowError, preset


@dataclass
class FakeStep:
    id: str
    source_kinds: frozenset[ImageKind]
    accepts: frozenset[ImageKind]
    version: int = 1
    calls: list[str] = field(default_factory=list)
    fail_name: str | None = None
    cancel_name: str | None = None
    parameter_schema: Mapping[str, ParameterType] = field(default_factory=dict)
    required_parameters: frozenset[str] = frozenset()

    def output_kind(self, input_kind: ImageKind) -> ImageKind:
        if self.id == "raw_develop":
            return ImageKind.RASTER
        if self.id == "watermark":
            return ImageKind.JPEG
        if self.id == "export":
            return ImageKind.EXPORTED
        return input_kind

    def validate(self, item: PhotoItem, spec: StepSpec) -> None:
        if spec.params.get("invalid"):
            raise WorkflowError(f"Invalid parameters for {item.source.name}")

    def execute(self, artifact: Artifact, spec: StepSpec, context: StepContext) -> Artifact:
        self.calls.append(artifact.source.name)
        if artifact.source.name == self.fail_name:
            raise RuntimeError("synthetic step failure")
        if artifact.source.name == self.cancel_name:
            context.cancelled.set()
        context.progress(self.id)
        return Artifact(
            artifact.source,
            context.target if self.id == "export" else artifact.path,
            self.output_kind(artifact.kind),
            artifact.metadata,
        )


def registry() -> StepRegistry:
    all_sources = frozenset({ImageKind.JPEG, ImageKind.NEF})
    steps = [
        FakeStep("location", all_sources, all_sources),
        FakeStep("raw_develop", frozenset({ImageKind.NEF}), frozenset({ImageKind.NEF})),
        FakeStep("watermark", all_sources, frozenset({ImageKind.JPEG, ImageKind.RASTER})),
        FakeStep("export", all_sources, all_sources | frozenset({ImageKind.RASTER})),
    ]
    result = StepRegistry()
    for step in steps:
        result.register(step)
    return result


def photo(root: Path, name: str) -> PhotoItem:
    root.mkdir(parents=True, exist_ok=True)
    source = root / name
    source.write_bytes(b"synthetic input")
    return PhotoItem(source, root)


@pytest.mark.parametrize(
    ("preset_name", "source_name", "expected_name", "expected_steps"),
    [
        ("location_only", "a.jpg", "a.jpg", ("location", "export")),
        ("location_only", "a.NEF", "a.NEF", ("location", "export")),
        ("watermark_only", "a.jpg", "a_marked.jpg", ("watermark", "export")),
        ("watermark_only", "a.NEF", "a_marked.jpg", ("raw_develop", "watermark", "export")),
        (
            "location_and_watermark",
            "a.NEF",
            "a_marked.jpg",
            ("location", "raw_develop", "watermark", "export"),
        ),
    ],
)
def test_presets_plan_by_input_type(
    tmp_path: Path,
    preset_name: str,
    source_name: str,
    expected_name: str,
    expected_steps: tuple[str, ...],
) -> None:
    item = photo(tmp_path / "input", source_name)
    plan = build_plan(BatchJob((item,), preset(preset_name), tmp_path / "output"), registry())
    assert plan.items[0].target.name == expected_name
    assert tuple(step.spec.component_id for step in plan.items[0].steps) == expected_steps


def test_whole_batch_preflight_stops_before_execution(tmp_path: Path) -> None:
    first = photo(tmp_path / "input", "a.jpg")
    second = photo(tmp_path / "input", "b.jpg")
    output = tmp_path / "output"
    output.mkdir()
    (output / "b.jpg").write_bytes(b"existing")
    components = registry()
    with pytest.raises(WorkflowError, match="already exists"):
        build_plan(BatchJob((first, second), preset("location_only"), output), components)
    assert all(not components.get(name).calls for name in ("location", "export"))


def test_order_unknown_component_and_source_collision(tmp_path: Path) -> None:
    jpg = photo(tmp_path / "input", "a.jpg")
    nef = photo(tmp_path / "input", "a.NEF")
    components = registry()
    wrong = WorkflowSpec((StepSpec("watermark"), StepSpec("location"), StepSpec("export")))
    with pytest.raises(WorkflowError, match="location must precede watermark"):
        build_plan(BatchJob((jpg,), wrong, tmp_path / "output"), components)
    with pytest.raises(WorkflowError, match="Unknown component"):
        build_plan(
            BatchJob((jpg,), WorkflowSpec((StepSpec("plugin_from_config"),)), tmp_path / "output"),
            components,
        )
    with pytest.raises(WorkflowError, match="same output"):
        build_plan(
            BatchJob((jpg, nef), preset("watermark_only"), tmp_path / "output"),
            components,
        )


def test_new_reviewed_component_registers_without_main_window_changes(tmp_path: Path) -> None:
    item = photo(tmp_path / "input", "a.jpg")
    components = registry()
    components.register(FakeStep("audit", frozenset({ImageKind.JPEG}), frozenset({ImageKind.JPEG})))
    workflow = WorkflowSpec((StepSpec("audit"), StepSpec("export")))
    plan = build_plan(BatchJob((item,), workflow, tmp_path / "output"), components)
    assert run_plan(plan)[0].status == ItemStatus.SUCCESS
    assert components.get("audit").calls == ["a.jpg"]


def test_failure_isolation_cancel_and_source_change(tmp_path: Path) -> None:
    first = photo(tmp_path / "input", "a.jpg")
    second = photo(tmp_path / "input", "b.jpg")
    components = registry()
    components.get("location").fail_name = "a.jpg"
    plan = build_plan(
        BatchJob((first, second), preset("location_only"), tmp_path / "output"), components
    )
    results = run_plan(plan)
    assert [result.status for result in results] == [ItemStatus.FAILED, ItemStatus.SUCCESS]
    assert results[0].current_step == "location"
    assert results[1].output == tmp_path / "output/b.jpg"

    components.get("location").fail_name = None
    components.get("export").cancel_name = "a.jpg"
    cancelled = Event()
    results = run_plan(plan, cancelled)
    assert [result.status for result in results] == [ItemStatus.SUCCESS, ItemStatus.CANCELLED]

    changed = photo(tmp_path / "input", "c.jpg")
    changed_plan = build_plan(
        BatchJob((changed,), preset("location_only"), tmp_path / "output"), components
    )
    changed.source.write_bytes(b"changed after preflight")
    assert run_plan(changed_plan)[0].status == ItemStatus.FAILED


def test_component_parameter_schema_is_checked_before_running(tmp_path: Path) -> None:
    item = photo(tmp_path / "input", "a.jpg")
    components = registry()
    components.register(
        FakeStep(
            "annotate",
            frozenset({ImageKind.JPEG}),
            frozenset({ImageKind.JPEG}),
            parameter_schema={"label": "str"},
            required_parameters=frozenset({"label"}),
        )
    )
    for params, reason in (
        ({}, "Missing"),
        ({"label": 42}, "Invalid"),
        ({"label": "ok", "other": True}, "Unknown"),
    ):
        workflow = WorkflowSpec((StepSpec("annotate", params=params), StepSpec("export")))
        with pytest.raises(WorkflowError, match=reason):
            build_plan(BatchJob((item,), workflow, tmp_path / "output"), components)
    assert components.get("annotate").calls == []
    workflow = WorkflowSpec((StepSpec("annotate", params={"label": "ok"}), StepSpec("export")))
    assert (
        run_plan(build_plan(BatchJob((item,), workflow, tmp_path / "output"), components))[0].status
        == ItemStatus.SUCCESS
    )


def test_preflight_can_be_cancelled_without_creating_output(tmp_path: Path) -> None:
    source = tmp_path / "cancel.jpg"
    source.write_bytes(b"test")
    cancellation = Event()
    cancellation.set()
    registered = registry()
    with pytest.raises(WorkflowError, match="Preflight cancelled"):
        build_plan(
            BatchJob((PhotoItem(source, tmp_path),), preset("location_only"), tmp_path / "out"),
            registered,
            cancelled=cancellation,
        )
    assert not (tmp_path / "out").exists()
