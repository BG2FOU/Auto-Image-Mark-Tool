"""Benchmark instrumentation follows real calls, including static import aliases."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from threading import Barrier, Thread
from types import SimpleNamespace

import pytest
from PIL import Image

from aim_tool.domain import Artifact, BatchJob, ImageKind, ItemStatus, PhotoItem
from aim_tool.services import file_state, images, nef_gps, preview_base, watermark
from aim_tool.ui.workers import PreflightWorker
from aim_tool.workflow import engine, steps
from aim_tool.workflow.registry import StepRegistry, preset

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_metrics.py"
_SPEC = importlib.util.spec_from_file_location("aim_benchmark_metrics_test", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
Metrics = _MODULE.Metrics


def test_digest_counts_include_file_state_aliases_and_separate_assets(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    asset = tmp_path / "font.ttf"
    staged = tmp_path / "staged.jpg"
    source.write_bytes(b"source pixels")
    asset.write_bytes(b"font bytes")
    staged.write_bytes(b"new pixels")
    original = file_state.file_state
    with Metrics(source_paths=(source,), asset_paths=(asset,)) as metrics:
        metrics.phase = "automatic_preflight"
        assert steps.file_state is file_state.file_state
        assert preview_base.file_state is file_state.file_state
        steps.file_state(source)
        preview_base.file_state(asset)
        steps._sha256(source)
        images._digest(staged)
        with pytest.raises(FileNotFoundError):
            file_state.file_state(tmp_path / "missing")
    rows = metrics.digest_reads["automatic_preflight"]
    source_rows = rows["original_source"]
    assert sum(row["calls"] for row in source_rows.values()) == 2
    assert sum(row["logical_bytes"] for row in source_rows.values()) == 2 * source.stat().st_size
    assert rows["asset"]["aim_tool.services.file_state.file_state"]["logical_bytes"] == 10
    failures = rows["artifact_or_other"]["aim_tool.services.file_state.file_state"]
    assert failures["calls"] == 1 and failures["successful_calls"] == 0
    assert failures["logical_bytes"] == 0
    assert file_state.file_state is original


def test_render_and_nef_fingerprint_static_imports_are_measured(
    tmp_path: Path, synthetic_watermark_resources: watermark.WatermarkResources
) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (600, 400)).save(source)

    class Tool:
        def metadata(self, path: Path, *tags: str) -> dict[str, str]:
            if "-preview:all" in tags and "-ImageDataHash" not in tags:
                return {"MakerNotes:PreviewImage": "cd" * 32}
            if "-ImageDataHash" in tags:
                return {
                    "File:FileType": "NEF",
                    "File:ImageDataHash": "ab" * 32,
                    "ExifTool:Validate": "0 0 0",
                }
            return {"File:FileType": "NEF"}

        def _run_for_path(self, *args: object) -> str:
            return ""

    with Metrics() as metrics:
        metrics.phase = "execution"
        config = watermark.WatermarkConfig("aviation", "B-1356", date(2026, 10, 25))
        pixels = images.watermark_jpeg_pixels(source, config, synthetic_watermark_resources)
        pixels.pixels.close()
        steps.fingerprint_nef(Tool(), tmp_path / "source.nef")
        nef_gps.fingerprint_nef(Tool(), tmp_path / "source.nef")
        nef_gps.raw_diagnostics(Tool(), tmp_path / "source.nef")
    rows = metrics.stages["execution"]
    assert rows["aim_tool.services.watermark.render_watermark_region"]["calls"] == 1
    assert rows["aim_tool.services.nef_gps.fingerprint_nef"]["calls"] == 2
    assert rows["aim_tool.services.nef_gps.raw_diagnostics"]["calls"] >= 1


def test_real_dispatch_and_commit_milestones_are_observed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    barrier = Barrier(2)

    def validate(self, photo, spec):
        return None

    def execute(self, artifact, spec, context):
        barrier.wait(timeout=5)
        staged = context.scratch / artifact.source.name
        staged.write_bytes(artifact.source.read_bytes())
        return Artifact(artifact.source, staged, ImageKind.JPEG, artifact.metadata)

    monkeypatch.setattr(steps.LocationStep, "validate", validate)
    monkeypatch.setattr(steps.LocationStep, "execute", execute)
    registry = StepRegistry()
    registry.register(steps.LocationStep(object()))
    registry.register(steps.ExportStep())
    photos = []
    for index in range(2):
        source = tmp_path / f"source-{index}.jpg"
        source.write_bytes(b"synthetic pixels")
        photos.append(PhotoItem(source, tmp_path))
    with Metrics() as metrics:
        metrics.phase = "automatic_preflight"
        plan = engine.build_plan(
            BatchJob(tuple(photos), preset("location_only"), tmp_path / "out"), registry
        )
        metrics.begin_action("automatic_preflight")
        results = engine.run_plan(plan, workers=2)
        metrics.mark("batch_completed_seconds")
    assert all(result.status == ItemStatus.SUCCESS for result in results)
    assert metrics.preflight_seconds["automatic_preflight"] > 0
    assert metrics.execution_seconds > 0
    assert metrics.configured_workers == [2]
    assert metrics.peak_active_items == 2
    assert len(metrics.photo_seconds) == 2
    assert (
        0
        <= metrics.milestones["first_item_preparation_started_seconds"]
        <= metrics.milestones["first_output_committed_seconds"]
        <= metrics.milestones["core_batch_completed_seconds"]
        <= metrics.milestones["batch_completed_seconds"]
    )


def test_first_preparation_finishes_for_the_same_photo_that_started_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = PhotoItem(tmp_path / "first.jpg", tmp_path)
    second = PhotoItem(tmp_path / "second.jpg", tmp_path)
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(_MODULE, "perf_counter", lambda: clock.now)

    def execute(plan, cancelled, progress, *, workers):
        clock.now = 103.0
        progress(first, "Preparing current source")
        clock.now = 104.0
        progress(second, "Preparing current source")
        clock.now = 106.0
        progress(second, "Prepared current source")
        assert "first_item_preparation_finished_seconds" not in metrics.milestones
        clock.now = 110.0
        progress(first, "Prepared current source")
        clock.now = 112.0
        progress(first, "Prepared current source")
        return ()

    monkeypatch.setattr(engine, "run_plan", execute)
    plan = SimpleNamespace(items=(SimpleNamespace(photo=first), SimpleNamespace(photo=second)))
    with Metrics() as metrics:
        metrics.begin_action("execution")
        engine.run_plan(plan, workers=2)
    assert metrics.first_preparation_photo_id == str(first.id)
    assert metrics.milestones["first_item_preparation_started_seconds"] == 3.0
    assert metrics.milestones["first_item_preparation_finished_seconds"] == 10.0
    assert metrics.milestones["first_item_preparation_duration_seconds"] == 7.0


def test_failed_first_preparation_does_not_take_a_later_photos_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = PhotoItem(tmp_path / "first.jpg", tmp_path)
    second = PhotoItem(tmp_path / "second.jpg", tmp_path)

    def execute(plan, cancelled, progress, *, workers):
        progress(first, "Preparing current source")
        progress(second, "Preparing current source")
        progress(second, "Prepared current source")
        return ()

    monkeypatch.setattr(engine, "run_plan", execute)
    plan = SimpleNamespace(items=(SimpleNamespace(photo=first), SimpleNamespace(photo=second)))
    with Metrics() as metrics:
        metrics.begin_action("execution")
        engine.run_plan(plan)
    assert metrics.first_preparation_photo_id == str(first.id)
    assert "first_item_preparation_finished_seconds" not in metrics.milestones
    assert "first_item_preparation_duration_seconds" not in metrics.milestones


def test_preflight_stages_keep_their_thread_phase_when_execution_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"pixels")

    def preflight(worker):
        file_state.file_state(source)

        def execution():
            metrics.phase = "execution"
            file_state.file_state(source)

        other = Thread(target=execution)
        other.start()
        other.join(timeout=5)
        assert not other.is_alive()
        file_state.file_state(source)

    monkeypatch.setattr(PreflightWorker, "run", preflight)
    with Metrics(source_paths=(source,)) as metrics:
        metrics.phase = "automatic_preflight"
        PreflightWorker.run(object())
    label = "aim_tool.services.file_state.file_state"
    assert metrics.stages["automatic_preflight"][label]["calls"] == 2
    assert metrics.stages["execution"][label]["calls"] == 1
    assert metrics.stages["automatic_preflight"]["PreflightWorker.run"]["calls"] == 1
