"""Real ExifTool GPS checks; private samples stay in data/ and are never changed."""

from __future__ import annotations

import shutil
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
import rawpy
from PIL import Image

from aim_tool.domain import BatchJob, PhotoItem
from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tool(pytestconfig: pytest.Config) -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(str(error))
        pytest.skip(str(error))


def _sample(path: Path, pytestconfig: pytest.Config) -> Path:
    if path.is_file():
        return path
    if pytestconfig.getoption("--require-real-assets"):
        pytest.fail(f"Required private sample is missing: {path}")
    pytest.skip(f"Private sample is missing: {path}")


def _registry(
    tool: ExifTool, clear_auxiliary: bool = False, *, allow_nef: bool = False
) -> StepRegistry:
    registry = StepRegistry()
    registry.register(
        LocationStep(
            tool, clear_auxiliary_gps=clear_auxiliary, allow_nef_after_viewer_check=allow_nef
        )
    )
    registry.register(ExportStep())
    return registry


def test_synthetic_jpeg_gps_roundtrip_pixels_and_source(tmp_path: Path, tool: ExifTool) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    source = input_root / "one.jpg"
    Image.new("RGB", (64, 48), (20, 80, 120)).save(source)
    original = sha256(source.read_bytes()).hexdigest()
    item = PhotoItem(source, input_root, coordinates=(-24.123456789, 118.987654321))
    plan = build_plan(
        BatchJob((item,), preset("location_only"), tmp_path / "output"), _registry(tool)
    )
    result = run_plan(plan)[0]
    assert result.output is not None, result.error
    gps = tool.read_gps(result.output)
    assert gps is not None
    assert abs(gps.latitude + 24.123456789) <= 1e-6
    assert abs(gps.longitude - 118.987654321) <= 1e-6
    assert sha256(source.read_bytes()).hexdigest() == original
    with Image.open(source) as before, Image.open(result.output) as after:
        assert before.size == after.size
        assert before.tobytes() == after.tobytes()


def test_old_auxiliary_gps_requires_clearance(tmp_path: Path, tool: ExifTool) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    source = input_root / "old.jpg"
    Image.new("RGB", (32, 24)).save(source)
    tool._run("-overwrite_original", "-GPS:GPSAltitude=120", str(source))
    item = PhotoItem(source, input_root, coordinates=(0.0, 0.0))
    job = BatchJob((item,), preset("location_only"), tmp_path / "output")
    with pytest.raises(ValueError, match="auxiliary GPS"):
        build_plan(job, _registry(tool))
    result = run_plan(build_plan(job, _registry(tool, clear_auxiliary=True)))[0]
    assert result.output is not None
    assert tool.read_gps(result.output) is not None
    assert "GPS:GPSAltitude" not in tool.metadata(result.output, "-GPS:GPSAltitude")


def test_real_nikon_jpeg_copy_preserves_pixels(
    tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config
) -> None:
    source = _sample(ROOT / "data/DSC_0168.jpg", pytestconfig)
    original = sha256(source.read_bytes()).hexdigest()
    item = PhotoItem(source, source.parent, coordinates=(0.0, 0.0))
    result = run_plan(
        build_plan(
            BatchJob((item,), preset("location_only"), tmp_path / "output"),
            _registry(tool),
        )
    )[0]
    assert result.output is not None, result.error
    assert tool.read_gps(result.output) is not None
    assert sha256(source.read_bytes()).hexdigest() == original
    with Image.open(source) as before, Image.open(result.output) as after:
        assert before.size == after.size
        assert sha256(before.tobytes()).digest() == sha256(after.tobytes()).digest()


@pytest.mark.raw
def test_nikon_nef_batch_remains_blocked_without_viewer_check(
    tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config
) -> None:
    source = _sample(ROOT / "data/DSC_0168.NEF", pytestconfig)
    item = PhotoItem(source, source.parent, coordinates=(24.478123, 118.085456))
    with pytest.raises(ValueError, match="independent Nikon viewer approval"):
        build_plan(
            BatchJob((item,), preset("location_only"), tmp_path / "output"),
            _registry(tool),
        )
    assert not (tmp_path / "output").exists()


@pytest.mark.raw
def test_nikon_nef_diagnostic_copy_preserves_raw_and_preview_pixels(
    tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config
) -> None:
    source = _sample(ROOT / "data/DSC_0168.NEF", pytestconfig)
    candidate = tmp_path / source.name
    shutil.copy2(source, candidate)
    source_hash = sha256(source.read_bytes()).hexdigest()
    fields = ("-Make", "-Model", "-SerialNumber", "-ShutterCount", "-LensModel")
    before_metadata = tool.metadata(source, *fields)
    before_metadata.pop("SourceFile", None)
    before_makernotes = tool.metadata(source, "-MakerNotes:all")
    before_makernotes.pop("SourceFile", None)
    before_makernotes.pop("PreviewIFD:PreviewImageStart", None)
    before_validation = tool.metadata(source, "-validate", "-warning", "-error")
    before_validation.pop("SourceFile", None)

    def fingerprint(path: Path) -> tuple[object, bytes, bytes]:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
            with Image.open(BytesIO(thumb.data)) as preview:
                return (
                    raw.sizes,
                    sha256(raw.raw_image_visible.tobytes()).digest(),
                    sha256(preview.convert("RGB").tobytes()).digest(),
                )

    before = fingerprint(source)
    tool.write_gps(candidate, 0.0, 0.0)
    after = fingerprint(candidate)
    after_metadata = tool.metadata(candidate, *fields)
    after_metadata.pop("SourceFile", None)
    after_makernotes = tool.metadata(candidate, "-MakerNotes:all")
    after_makernotes.pop("SourceFile", None)
    # ExifTool may relocate the embedded preview; its decoded pixels are checked above.
    after_makernotes.pop("PreviewIFD:PreviewImageStart", None)
    after_validation = tool.metadata(candidate, "-validate", "-warning", "-error")
    after_validation.pop("SourceFile", None)
    assert before == after
    assert before_metadata == after_metadata
    assert before_makernotes == after_makernotes
    assert before_validation == after_validation
    assert sha256(source.read_bytes()).hexdigest() == source_hash
    # Independent Nikon viewer approval is still required before batch NEF output is enabled.


@pytest.mark.raw
def test_nikon_nef_transactional_batch_preserves_format_and_payloads(
    tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config
) -> None:
    from aim_tool.services.nef_gps import fingerprint_nef

    source = _sample(ROOT / "data/DSC_0168.NEF", pytestconfig)
    source_hash = sha256(source.read_bytes()).digest()
    before = fingerprint_nef(tool, source)
    item = PhotoItem(source, source.parent, coordinates=(-24.123456, -118.654321))
    output = tmp_path / "output"
    (result,) = run_plan(
        build_plan(
            BatchJob((item,), preset("location_only"), output),
            _registry(tool, allow_nef=True),
        )
    )
    assert result.output == output / source.name, result.error
    assert fingerprint_nef(tool, result.output) == before
    gps = tool.read_gps(result.output)
    assert gps is not None
    assert abs(gps.latitude + 24.123456) < 1e-6
    assert abs(gps.longitude + 118.654321) < 1e-6
    assert sha256(source.read_bytes()).digest() == source_hash
    assert not list(output.glob("*.jpg"))
    assert not list(output.glob(".aim-*"))


@pytest.mark.raw
def test_nef_changed_payload_is_not_committed(
    tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _sample(ROOT / "data/DSC_0168.NEF", pytestconfig)
    original = sha256(source.read_bytes()).digest()
    write_gps = tool.write_gps

    def corrupt_copy(path: Path, latitude: float, longitude: float) -> None:
        write_gps(path, latitude, longitude)
        offset = tool.metadata(path, "-SubIFD1:StripOffsets")["SubIFD1:StripOffsets"]
        with path.open("r+b") as copy:
            copy.seek(offset)
            byte = copy.read(1)
            copy.seek(offset)
            copy.write(bytes([byte[0] ^ 0xFF]))

    monkeypatch.setattr(tool, "write_gps", corrupt_copy)
    item = PhotoItem(source, source.parent, coordinates=(0, 0))
    output = tmp_path / "output"
    (result,) = run_plan(
        build_plan(
            BatchJob((item,), preset("location_only"), output),
            _registry(tool, allow_nef=True),
        )
    )
    assert result.output is None
    assert "NEF RAW, previews or camera metadata changed" in (result.error or "")
    assert sha256(source.read_bytes()).digest() == original
    assert not list(output.iterdir())


@pytest.mark.raw
def test_gui_mixed_jpg_nef_gps_batch_without_conversion_or_watermark_assets(
    qtbot, tmp_path: Path, tool: ExifTool, pytestconfig: pytest.Config
) -> None:
    from aim_tool.domain import ItemStatus
    from aim_tool.services.nef_gps import fingerprint_nef
    from aim_tool.services.storage import ConfigStore, WatermarkSettingsStore
    from aim_tool.ui.main_window import MainWindow

    source = _sample(ROOT / "data/DSC_0168.NEF", pytestconfig)
    original = sha256(source.read_bytes()).digest()
    before = fingerprint_nef(tool, source)
    jpeg = tmp_path / "jpg/a.jpg"
    jpeg.parent.mkdir()
    Image.new("RGB", (64, 48), (20, 80, 120)).save(jpeg)
    window = MainWindow(
        settings_store=WatermarkSettingsStore(tmp_path / "settings.json"),
        location_store=ConfigStore(tmp_path / "locations.json"),
        workflow_store=ConfigStore(tmp_path / "workflows.json"),
        allow_nef_after_viewer_check=True,
    )
    qtbot.addWidget(window)
    window.show()
    try:
        window.workflow.presets.setCurrentIndex(1)
        window.add_photos((source, jpeg))
        window.apply_coordinates(0, 0)
        output = tmp_path / "output"
        window.output_edit.setText(str(output))
        window.start()
        qtbot.waitUntil(lambda: not window._busy, timeout=30000)
        assert len(window.results) == 2, window.log.toPlainText()
        assert all(result.status == ItemStatus.SUCCESS for result in window.results)
        assert {path.name for path in output.iterdir()} == {source.name, jpeg.name}
        assert fingerprint_nef(tool, output / source.name) == before
        assert sha256(source.read_bytes()).digest() == original
        with Image.open(jpeg) as first, Image.open(output / jpeg.name) as second:
            assert first.tobytes() == second.tobytes()
    finally:
        window.close()
        qtbot.waitUntil(lambda: not window.has_active_workers, timeout=20000)
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
