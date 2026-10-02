"""Real JPG watermark pipelines with synthetic public test assets."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from threading import Event

import pytest
from PIL import Image, ImageCms

from aim_tool.domain import BatchJob, ItemStatus, PhotoItem
from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.resources import local_project_resources
from aim_tool.services.watermark import WatermarkResources
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep, RawDevelopStep, WatermarkStep

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tool(pytestconfig: pytest.Config) -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(str(error))
        pytest.skip(str(error))


@pytest.fixture
def resources(synthetic_watermark_resources: WatermarkResources) -> WatermarkResources:
    return synthetic_watermark_resources


def _registry(tool: ExifTool, resources: WatermarkResources) -> StepRegistry:
    registry = StepRegistry()
    registry.register(LocationStep(tool, clear_auxiliary_gps=True))
    registry.register(RawDevelopStep())
    registry.register(WatermarkStep(tool, resources))
    registry.register(ExportStep())
    return registry


def _photo(tmp_path: Path, name: str, tool: ExifTool, *, profile: bool = True) -> PhotoItem:
    root = tmp_path / "input"
    root.mkdir(exist_ok=True)
    source = root / name
    image = Image.new("RGB", (1203, 803), (20, 40, 60))
    exif = Image.Exif()
    exif[274] = 6
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes() if profile else None
    image.save(source, exif=exif, icc_profile=icc, dpi=(300, 300))
    tool._run_for_path(
        source,
        "-overwrite_original",
        "-ExifIFD:DateTimeOriginal=2026:09:13 12:57:36",
        "-IFD0:Make=TEST",
        "-IFD0:Copyright=Original copyright",
    )
    return PhotoItem(
        source,
        root,
        edits={"category": "aviation", "subject": "B-1356"},
        coordinates=(-24.2, 118.4),
    )


@pytest.mark.parametrize("workflow", ["watermark_only", "location_and_watermark"])
def test_jpg_pipeline_keeps_authoritative_gps_orientation_date_and_source(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources, workflow: str
) -> None:
    photo = _photo(tmp_path, "中文 -源片.JPEG", tool)
    tool.write_gps(photo.source, 1, 2)
    before = sha256(photo.source.read_bytes()).digest()
    result = run_plan(
        build_plan(
            BatchJob((photo,), preset(workflow), tmp_path / "output"), _registry(tool, resources)
        )
    )[0]
    assert result.status == ItemStatus.SUCCESS, result.error
    assert result.output is not None and result.output.name == "中文 -源片_marked.jpg"
    gps = tool.read_gps(result.output)
    assert gps is not None
    expected = (1, 2) if workflow == "watermark_only" else photo.coordinates
    assert expected is not None
    assert abs(gps.latitude - expected[0]) <= 1e-6
    assert abs(gps.longitude - expected[1]) <= 1e-6
    values = tool.metadata(result.output)
    assert values["ExifIFD:DateTimeOriginal"] == "2026:09:13 12:57:36"
    assert values["IFD0:Copyright"] == "Original copyright"
    assert values["IFD0:Orientation"] == 1
    with Image.open(result.output) as image:
        assert image.size == (803, 1203)
        assert image.info["icc_profile"]
        assert image.info["dpi"] == (300, 300)
        assert image.getpixel((image.width - 8, image.height - 8)) != image.getpixel((0, 0))
    assert sha256(photo.source.read_bytes()).digest() == before
    assert not list((tmp_path / "output").glob(".aim-*"))


def test_missing_profile_warning_is_in_result(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources
) -> None:
    photo = _photo(tmp_path, "a.jpg", tool, profile=False)
    result = run_plan(
        build_plan(
            BatchJob((photo,), preset("watermark_only"), tmp_path / "output"),
            _registry(tool, resources),
        )
    )[0]
    assert result.status == ItemStatus.SUCCESS, result.error
    assert result.warnings == ("No ICC profile; assumed sRGB for preview",)


def test_metadata_failure_is_isolated_and_leaves_no_failed_output(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _photo(tmp_path, "bad.jpg", tool)
    second = _photo(tmp_path, "good.jpg", tool)
    original = tool.copy_tags

    def fail_one(
        source: Path, target: Path, tags: tuple[str, ...], overrides: dict[str, int]
    ) -> None:
        if source.name == "bad.jpg":
            raise ExifToolError("Injected metadata transfer failure")
        original(source, target, tags, overrides)

    monkeypatch.setattr(tool, "copy_tags", fail_one)
    plan = build_plan(
        BatchJob((first, second), preset("watermark_only"), tmp_path / "output"),
        _registry(tool, resources),
    )
    results = run_plan(plan)
    assert [result.status for result in results] == [ItemStatus.FAILED, ItemStatus.SUCCESS]
    assert results[0].current_step == "watermark"
    assert not (tmp_path / "output/bad_marked.jpg").exists()
    assert not list((tmp_path / "output").glob(".aim-*"))


def test_cancel_before_commit_cleans_current_artifact(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources
) -> None:
    photo = _photo(tmp_path, "a.jpg", tool)
    signal = Event()
    plan = build_plan(
        BatchJob((photo,), preset("watermark_only"), tmp_path / "output"),
        _registry(tool, resources),
    )

    def cancel_on_render(photo: PhotoItem, message: str) -> None:
        if message.startswith("Watermark and metadata"):
            signal.set()

    result = run_plan(plan, signal, cancel_on_render)[0]
    assert result.status == ItemStatus.CANCELLED
    assert not (tmp_path / "output/a_marked.jpg").exists()
    assert not list((tmp_path / "output").glob(".aim-*"))


def test_asset_changed_after_preflight_rejects_export(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources
) -> None:
    photo = _photo(tmp_path, "a.jpg", tool)
    plan = build_plan(
        BatchJob((photo,), preset("watermark_only"), tmp_path / "output"),
        _registry(tool, resources),
    )
    with resources.signature.open("ab") as output:
        output.write(b"changed")
    result = run_plan(plan)[0]
    assert result.status == ItemStatus.FAILED
    assert "asset changed" in (result.error or "")
    assert not (tmp_path / "output/a_marked.jpg").exists()


def test_nef_watermark_remains_blocked_before_any_output(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources
) -> None:
    source = tmp_path / "a.NEF"
    source.write_bytes(b"not processed")
    item = PhotoItem(source, tmp_path)
    with pytest.raises(ValueError, match="NEF watermark processing is deferred"):
        build_plan(
            BatchJob((item,), preset("watermark_only"), tmp_path / "output"),
            _registry(tool, resources),
        )
    assert not (tmp_path / "output").exists()


@pytest.mark.visual
def test_private_nikon_jpg_combined_pipeline(
    tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config
) -> None:
    resources = local_project_resources(ROOT)
    source = ROOT / "data/DSC_0168.jpg"
    if not all(path.is_file() for path in (source, resources.latin_font, resources.signature)):
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail("Local Nikon JPG and private resources are required")
        pytest.skip("Private Nikon sample/resources stay local")
    before = sha256(source.read_bytes()).digest()
    photo = PhotoItem(
        source,
        source.parent,
        edits={"category": "aviation", "subject": "LX-VCF"},
        coordinates=(0, 0),
    )
    result = run_plan(
        build_plan(
            BatchJob((photo,), preset("location_and_watermark"), tmp_path / "output"),
            _registry(tool, resources),
        )
    )[0]
    assert result.status == ItemStatus.SUCCESS, result.error
    assert result.output is not None
    gps = tool.read_gps(result.output)
    assert gps is not None and gps.latitude == gps.longitude == 0
    values = tool.metadata(result.output)
    assert values["IFD0:Model"] == "NIKON Z 5"
    assert values["ExifIFD:DateTimeOriginal"] == "2026:09:13 12:57:36"
    assert sha256(source.read_bytes()).digest() == before


@pytest.mark.parametrize("invalid", ["partial_gps", "missing_date"])
def test_bad_source_metadata_blocks_batch_in_preflight(
    tmp_path: Path, tool: ExifTool, resources: WatermarkResources, invalid: str
) -> None:
    photo = _photo(tmp_path, "a.jpg", tool)
    if invalid == "partial_gps":
        tool._run_for_path(photo.source, "-overwrite_original", "-GPS:GPSLatitude=1")
        message = "incomplete"
        expected_error = ExifToolError
    else:
        tool._run_for_path(photo.source, "-overwrite_original", "-ExifIFD:DateTimeOriginal=")
        message = "Capture date is missing"
        expected_error = ValueError
    before = sha256(photo.source.read_bytes()).digest()
    with pytest.raises(expected_error, match=message):
        build_plan(
            BatchJob((photo,), preset("watermark_only"), tmp_path / "output"),
            _registry(tool, resources),
        )
    assert not (tmp_path / "output").exists()
    assert sha256(photo.source.read_bytes()).digest() == before
