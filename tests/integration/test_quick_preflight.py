"""Quick checks defer expensive reads while binding execution to current source content."""

from __future__ import annotations

import os
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from aim_tool.domain import BatchJob, ItemStatus, PhotoItem
from aim_tool.services.exiftool import ExifTool
from aim_tool.services.watermark import WatermarkResources
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep, RawDevelopStep, WatermarkStep


@pytest.fixture
def tool():
    with ExifTool(persistent=True) as instance:
        yield instance


def photo(tmp_path: Path, name: str = "source.jpg") -> PhotoItem:
    source = tmp_path / "input" / name
    source.parent.mkdir(exist_ok=True)
    exif = Image.Exif()
    exif[274] = 6
    exif[34665] = {36867: "2026:10:09 12:00:00"}
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (900, 600), (20, 40, 60)).save(source, exif=exif, icc_profile=icc)
    return PhotoItem(
        source,
        source.parent,
        coordinates=(24.2, 118.4),
        edits={"category": "aviation", "subject": "B-1356"},
    )


def registry(tool: ExifTool, resources: WatermarkResources, *, clear: bool = True) -> StepRegistry:
    result = StepRegistry()
    result.register(LocationStep(tool, clear_auxiliary_gps=clear))
    result.register(RawDevelopStep())
    result.register(WatermarkStep(tool, resources))
    result.register(ExportStep())
    return result


@pytest.mark.parametrize("workflow", ["watermark_only", "location_and_watermark"])
def test_quick_plan_does_not_read_source_metadata_hash_or_pixels(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources, monkeypatch, workflow: str
) -> None:
    from aim_tool.services import images
    from aim_tool.workflow import engine

    item = photo(tmp_path)
    components = registry(tool, synthetic_watermark_resources)

    def forbidden(*args, **kwargs):
        raise AssertionError("Expensive source preflight was called")

    with monkeypatch.context() as checks:
        checks.setattr(tool, "metadata", forbidden)
        checks.setattr(engine, "file_state", forbidden)
        checks.setattr(images, "validate_jpeg", forbidden)
        plan = build_plan(
            BatchJob((item,), preset(workflow), tmp_path / "out"), components, mode="quick"
        )
    result = run_plan(plan)[0]
    assert result.status == ItemStatus.SUCCESS, result.error
    assert not components.get("watermark")._prepared


@pytest.mark.parametrize("workflow", ["watermark_only", "location_and_watermark"])
def test_quick_and_full_have_identical_pixels_and_metadata(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources, workflow: str
) -> None:
    item = photo(tmp_path)
    before = sha256(item.source.read_bytes()).digest()
    outputs = []
    for mode in ("full", "quick"):
        result = run_plan(
            build_plan(
                BatchJob((item,), preset(workflow), tmp_path / mode),
                registry(tool, synthetic_watermark_resources),
                mode=mode,
            )
        )[0]
        assert result.status == ItemStatus.SUCCESS, result.error
        assert result.output is not None
        with Image.open(result.output) as image:
            outputs.append((image.size, image.tobytes()))
        metadata = tool.metadata(result.output, "-ExifIFD:DateTimeOriginal", "-GPS:all")
        metadata.pop("SourceFile", None)
        outputs.append(metadata)
    assert outputs[:2] == outputs[2:]
    assert sha256(item.source.read_bytes()).digest() == before


def test_quick_prepare_uses_current_exif_after_same_stat_replacement(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources
) -> None:
    item = photo(tmp_path)
    item = replace(item, metadata={"ExifIFD:DateTimeOriginal": "1999:01:01 00:00:00"})
    plan = build_plan(
        BatchJob((item,), preset("watermark_only"), tmp_path / "out"),
        registry(tool, synthetic_watermark_resources),
        mode="quick",
    )
    previous = item.source.stat()
    tool._run_for_path(
        item.source, "-overwrite_original", "-ExifIFD:DateTimeOriginal=2026:10:25 12:00:00"
    )
    assert item.source.stat().st_size == previous.st_size
    os.utime(item.source, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    messages = []
    result = run_plan(plan, progress=lambda _, message: messages.append(message))[0]
    assert result.status == ItemStatus.SUCCESS, result.error
    assert result.output is not None
    assert (
        tool.metadata(result.output, "-ExifIFD:DateTimeOriginal")["ExifIFD:DateTimeOriginal"]
        == "2026:10:25 12:00:00"
    )
    assert any("date source: EXIF DateTimeOriginal" in message for message in messages)


def test_quick_prepare_rejects_changed_dimensions_before_decode(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources, monkeypatch
) -> None:
    item = photo(tmp_path)
    plan = build_plan(
        BatchJob((item,), preset("watermark_only"), tmp_path / "out"),
        registry(tool, synthetic_watermark_resources),
        mode="quick",
    )
    Image.new("RGB", (1800, 1200)).save(item.source)

    def forbidden(*args, **kwargs):
        raise AssertionError("Changed dimensions were decoded before admission")

    monkeypatch.setattr("aim_tool.services.images.prepare_jpeg", forbidden)
    result = run_plan(plan)[0]
    assert result.status == ItemStatus.FAILED and "dimensions changed" in str(result.error)
    assert not plan.items[0].target.exists()


@pytest.mark.parametrize("workflow", ["watermark_only", "location_and_watermark"])
def test_quick_source_binding_covers_all_steps_until_commit(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources, monkeypatch, workflow: str
) -> None:
    from aim_tool.services import images

    item = photo(tmp_path)
    plan = build_plan(
        BatchJob((item,), preset(workflow), tmp_path / "out"),
        registry(tool, synthetic_watermark_resources),
        mode="quick",
    )
    original = images._encode_watermark_jpeg

    def mutate(*args, **kwargs):
        value = original(*args, **kwargs)
        tool._run_for_path(item.source, "-overwrite_original", "-IFD0:Make=CHANGED")
        return value

    monkeypatch.setattr(images, "_encode_watermark_jpeg", mutate)
    result = run_plan(plan)[0]
    assert result.status == ItemStatus.FAILED and "Source changed" in str(result.error)
    assert not plan.items[0].target.exists()


@pytest.mark.parametrize("invalid", ["partial_gps", "auxiliary", "missing_date"])
def test_quick_metadata_errors_are_rejected_before_writing_gps(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources, monkeypatch, invalid: str
) -> None:
    item = photo(tmp_path)
    tags = {
        "partial_gps": ("-GPS:GPSLatitude=1",),
        "auxiliary": ("-GPS:GPSSpeed=30",),
        "missing_date": ("-ExifIFD:DateTimeOriginal=",),
    }[invalid]
    tool._run_for_path(item.source, "-overwrite_original", *tags)
    plan = build_plan(
        BatchJob((item,), preset("location_and_watermark"), tmp_path / "out"),
        registry(tool, synthetic_watermark_resources, clear=invalid != "auxiliary"),
        mode="quick",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("GPS was written before source metadata rejection")

    monkeypatch.setattr(tool, "write_gps", forbidden)
    result = run_plan(plan)[0]
    assert result.status == ItemStatus.FAILED and "GPS was written" not in str(result.error)
    assert not plan.items[0].target.exists()


def test_quick_parallel_failure_isolation_and_resource_binding(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources
) -> None:
    items = tuple(photo(tmp_path, f"{name}.jpg") for name in "abc")
    data = items[1].source.read_bytes()
    items[1].source.write_bytes(data[:-100])
    plan = build_plan(
        BatchJob(items, preset("watermark_only"), tmp_path / "out"),
        registry(tool, synthetic_watermark_resources),
        mode="quick",
    )
    results = run_plan(plan, workers=2)
    assert [result.status for result in results] == [
        ItemStatus.SUCCESS,
        ItemStatus.FAILED,
        ItemStatus.SUCCESS,
    ]
    assert [result.photo_id for result in results] == [item.id for item in items]
    assert not list((tmp_path / "out").glob(".aim-*"))
