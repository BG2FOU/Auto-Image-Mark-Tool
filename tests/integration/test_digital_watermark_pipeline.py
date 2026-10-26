"""Real ExifTool + frequency watermark export with generated public assets."""

from dataclasses import replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from threading import Event

import numpy as np
import pytest
from PIL import Image, ImageCms, ImageDraw

from aim_tool.domain import BatchJob, ItemStatus, PhotoItem, StepSpec, WorkflowSpec
from aim_tool.services import frequency_watermark as frequency
from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.watermark import WatermarkResources
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry
from aim_tool.workflow.steps import ExportStep, LocationStep, WatermarkStep

KEY = "b" * 64


@pytest.fixture
def tool(pytestconfig: pytest.Config) -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(str(error))
        pytest.skip(str(error))


def setup(
    tmp_path: Path,
    tool: ExifTool,
    resources: WatermarkResources,
    algorithm: str,
    level: str,
    *,
    small: bool = False,
) -> tuple[BatchJob, StepRegistry, WatermarkResources]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = source_root / "中文 源片.jpg"
    size = (600, 400) if small else (3840, 3200)
    gradient = Image.linear_gradient("L").resize(size).point(lambda p: round(35 + p * 0.7))
    exif = Image.Exif()
    exif[274] = 6
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    gradient.convert("RGB").save(source, quality=95, exif=exif, icc_profile=icc, dpi=(300, 300))
    tool._run_for_path(
        source,
        "-overwrite_original",
        "-ExifIFD:DateTimeOriginal=2026:10:13 08:00:00",
        "-IFD0:Copyright=Public synthetic fixture",
    )
    signature = tmp_path / "strokes.png"
    image = Image.new("RGBA", (100, 60))
    ImageDraw.Draw(image).line(
        [(5, 50), (30, 5), (55, 50), (80, 8), (95, 35)], fill="white", width=5
    )
    image.save(signature)
    resources = replace(resources, signature=signature)
    photo = PhotoItem(
        source,
        source_root,
        taken_on=date(2026, 10, 13),
        edits={"category": "aviation", "subject": "B-1356"},
        coordinates=(24.3, 118.2),
    )
    params = {
        "digital_enabled": True,
        "digital_algorithm": algorithm,
        "digital_level": level,
        "digital_key": KEY,
    }
    job = BatchJob(
        (photo,),
        WorkflowSpec(
            (StepSpec("location"), StepSpec("watermark", params=params), StepSpec("export"))
        ),
        tmp_path / "out",
    )
    registry = StepRegistry()
    for component in (LocationStep(tool), WatermarkStep(tool, resources), ExportStep()):
        registry.register(component)
    return job, registry, resources


@pytest.mark.parametrize("algorithm", ["dct", "fft"])
@pytest.mark.parametrize("level", ["low", "medium", "high"])
@pytest.mark.parametrize("mode", ["full", "quick"])
def test_all_six_choices_recover_after_metadata_and_keep_source(
    tmp_path: Path,
    tool: ExifTool,
    synthetic_watermark_resources: WatermarkResources,
    algorithm: str,
    level: str,
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, registry, resources = setup(
        tmp_path, tool, synthetic_watermark_resources, algorithm, level
    )
    source = job.photos[0].source
    before = sha256(source.read_bytes()).digest()
    verified = []
    original_verify = frequency.verify_signature

    def verify_after_metadata(path, *args, **kwargs):
        values = tool.metadata(path, "-IFD0:Copyright")
        assert values["IFD0:Copyright"] == "Public synthetic fixture"
        verified.append(path)
        return original_verify(path, *args, **kwargs)

    monkeypatch.setattr(frequency, "verify_signature", verify_after_metadata)
    result = run_plan(build_plan(job, registry, mode=mode))[0]
    assert len(verified) == 1
    assert result.status == ItemStatus.SUCCESS, result.error
    assert result.output is not None
    with Image.open(result.output) as image:
        assert image.size == (3200, 3840)
        assert image.getexif()[274] == 1
        assert image.info["icc_profile"]
        assert image.info["dpi"] == (300, 300)
        pixels = np.asarray(image.convert("RGB"))
    config = frequency.digital_config(job.workflow.steps[1].params)
    assert config is not None
    spec, expected = frequency.signature_spec((3200, 3840), config, resources.signature)
    recovered = frequency.extract(pixels, spec, config.key)
    assert np.array_equal(expected, recovered)
    gps = tool.read_gps(result.output)
    assert gps is not None and abs(gps.latitude - 24.3) < 1e-6
    values = tool.metadata(result.output)
    assert values["ExifIFD:DateTimeOriginal"] == "2026:10:13 08:00:00"
    assert values["IFD0:Copyright"] == "Public synthetic fixture"
    assert KEY not in str(values)
    assert sha256(source.read_bytes()).digest() == before
    assert not list(job.output_root.glob(".aim-*"))


@pytest.mark.parametrize("damage", ["pixels", "jpeg", "cancel", "metadata"])
@pytest.mark.parametrize("mode", ["full", "quick"])
def test_final_gate_rejects_post_metadata_damage_or_cancellation(
    tmp_path: Path,
    tool: ExifTool,
    synthetic_watermark_resources: WatermarkResources,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
    mode: str,
) -> None:
    from aim_tool.services import metadata

    job, registry, _ = setup(tmp_path, tool, synthetic_watermark_resources, "dct", "medium")
    plan = build_plan(job, registry, mode=mode)
    stop = Event()
    original = metadata.preserve_watermark_metadata

    def damaged(adapter, authority, target):
        original(adapter, authority, target)
        if damage == "pixels":
            with Image.open(target) as image:
                size = image.size
            Image.new("RGB", size).save(target, quality=95)
        elif damage == "jpeg":
            target.write_bytes(target.read_bytes()[:200])
        elif damage == "cancel":
            stop.set()
        else:
            raise ExifToolError("Injected final metadata failure")

    monkeypatch.setattr(metadata, "preserve_watermark_metadata", damaged)
    result = run_plan(plan, stop)[0]
    assert result.status == (ItemStatus.CANCELLED if damage == "cancel" else ItemStatus.FAILED)
    assert not list(job.output_root.glob("*_marked.jpg"))
    assert not list(job.output_root.glob(".aim-*"))


def test_independent_export_keeps_its_own_complete_verification(
    tmp_path: Path,
    tool: ExifTool,
    synthetic_watermark_resources: WatermarkResources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aim_tool.services.images import export_watermark_preview

    job, registry, resources = setup(tmp_path, tool, synthetic_watermark_resources, "dct", "medium")
    step = registry.get("watermark")
    assert isinstance(step, WatermarkStep)
    config, _ = step.configuration(job.photos[0], job.workflow.steps[1])
    calls = 0
    original = frequency.verify_signature

    def verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(frequency, "verify_signature", verify)
    target = tmp_path / "independent/result.jpg"
    export_watermark_preview(job.photos[0].source, target, config, resources)
    assert calls == 1 and target.is_file()

    def fail(*args, **kwargs):
        raise ValueError("Injected independent verification failure")

    monkeypatch.setattr(frequency, "verify_signature", fail)
    with pytest.raises(ValueError, match="independent verification failure"):
        export_watermark_preview(
            job.photos[0].source, target.with_name("failed.jpg"), config, resources
        )
    assert not target.with_name("failed.jpg").exists()


def test_capacity_failure_happens_in_preflight_before_any_output(
    tmp_path: Path, tool: ExifTool, synthetic_watermark_resources: WatermarkResources
) -> None:
    job, registry, _ = setup(
        tmp_path, tool, synthetic_watermark_resources, "fft", "medium", small=True
    )
    with pytest.raises(ValueError, match="容量不足"):
        build_plan(job, registry)
    assert not job.output_root.exists()


def test_cancel_during_frequency_transform_is_cancelled_and_cleans_output(
    tmp_path: Path,
    tool: ExifTool,
    synthetic_watermark_resources: WatermarkResources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, registry, _ = setup(tmp_path, tool, synthetic_watermark_resources, "fft", "medium")
    plan = build_plan(job, registry)
    stop, calls = Event(), 0
    original = frequency.check_cancelled

    def cancel_in_transform(signal: Event | None) -> None:
        nonlocal calls
        calls += 1
        if calls == 5:
            stop.set()
        original(signal)

    monkeypatch.setattr(frequency, "check_cancelled", cancel_in_transform)
    result = run_plan(plan, stop)[0]
    assert result.status == ItemStatus.CANCELLED and result.error is None
    assert not list(job.output_root.glob("*_marked.jpg"))
    assert not list(job.output_root.glob(".aim-*"))


def test_failed_recovery_is_not_committed(
    tmp_path: Path,
    tool: ExifTool,
    synthetic_watermark_resources: WatermarkResources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, registry, _ = setup(tmp_path, tool, synthetic_watermark_resources, "dct", "medium")
    plan = build_plan(job, registry)
    original = frequency.extract

    def wrong_bits(*args: object, **kwargs: object) -> np.ndarray:
        result = original(*args, **kwargs)
        result[0, 0] = not result[0, 0]
        return result

    monkeypatch.setattr(frequency, "extract", wrong_bits)
    result = run_plan(plan)[0]
    assert result.status == ItemStatus.FAILED
    assert "未能完整恢复" in str(result.error)
    assert not list(job.output_root.glob("*_marked.jpg"))
    assert not list(job.output_root.glob(".aim-*"))
