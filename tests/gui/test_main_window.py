"""Full JPG workspace through native ExifTool, worker jobs and transactional outputs."""

from hashlib import sha256
from pathlib import Path
from threading import Event

import pytest
from PIL import Image, ImageCms
from pytestqt.qtbot import QtBot

from aim_tool.domain import ItemStatus
from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.storage import ConfigStore, WatermarkSettings, WatermarkSettingsStore
from aim_tool.services.watermark import WatermarkResources
from aim_tool.ui.main_window import MainWindow
from aim_tool.workflow.steps import WatermarkStep


@pytest.fixture
def tool(pytestconfig: pytest.Config) -> ExifTool:
    try:
        return ExifTool()
    except ExifToolError as error:
        if pytestconfig.getoption("--require-real-assets"):
            pytest.fail(str(error))
        pytest.skip(str(error))


def _photo(path: Path, *, dated: bool = True) -> None:
    path.parent.mkdir(exist_ok=True)
    exif = Image.Exif()
    exif[274] = 6
    if dated:
        exif[34665] = {36867: "2026:09:26 15:33:31"}
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (1007, 672), (30, 50, 70)).save(path, exif=exif, icc_profile=profile)


def _window(qtbot: QtBot, tmp_path: Path, resources: WatermarkResources) -> MainWindow:
    settings = WatermarkSettingsStore(tmp_path / "settings.json")
    settings.save(WatermarkSettings(resources))
    window = MainWindow(
        settings_store=settings,
        location_store=ConfigStore(tmp_path / "locations.json"),
        workflow_store=ConfigStore(tmp_path / "workflows.json"),
    )
    qtbot.addWidget(window)
    window.show()
    return window


def _close(qtbot: QtBot, window: MainWindow) -> None:
    window.close()
    qtbot.waitUntil(lambda: not window.has_active_workers, timeout=20000)
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)


def test_gui_combined_export_preserves_current_gps_and_source(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources, tool: ExifTool
) -> None:
    source = tmp_path / "input/中文.jpg"
    _photo(source)
    tool.write_gps(source, 1, 2)
    before = sha256(source.read_bytes()).digest()
    window = _window(qtbot, tmp_path, synthetic_watermark_resources)
    try:
        window.add_photos((source,))
        window.workflow.presets.setCurrentIndex(2)
        window.bulk_subject.setText("B-1356")
        window.bulk_date.setText("2026/9/26")
        window.apply_fields_button.click()
        window.apply_coordinates(-24.2, 118.4)
        output = tmp_path / "out"
        window.output_edit.setText(str(output))
        window.start_button.click()
        assert not window.start_button.isEnabled()
        assert window.cancel_button.isEnabled()
        qtbot.waitUntil(lambda: not window._busy, timeout=30000)
        assert len(window.results) == 1
        assert window.results[0].status == ItemStatus.SUCCESS, window.log.toPlainText()
        target = output / "中文_marked.jpg"
        gps = tool.read_gps(target)
        assert (
            gps is not None
            and abs(gps.latitude + 24.2) <= 1e-6
            and abs(gps.longitude - 118.4) <= 1e-6
        )
        assert tool.metadata(target)["ExifIFD:DateTimeOriginal"] == "2026:09:26 15:33:31"
        with Image.open(target) as image:
            assert image.size == (672, 1007) and image.getexif().get(274) == 1
        assert sha256(source.read_bytes()).digest() == before
        assert not list(output.glob(".aim-*"))
        report = tmp_path / "results.json"
        window.save_report(report)
        assert '"status": "success"' in report.read_text(encoding="utf-8")
        assert "latitude" not in report.read_text(encoding="utf-8")
    finally:
        _close(qtbot, window)


def test_gps_only_works_without_watermark_assets_or_capture_date(
    qtbot: QtBot, tmp_path: Path, tool: ExifTool
) -> None:
    missing = WatermarkResources(
        tmp_path / "missing.ttf", tmp_path / "missing2.ttf", tmp_path / "missing.png"
    )
    source = tmp_path / "input/a.JPEG"
    _photo(source, dated=False)
    original_pixels = Image.open(source).tobytes()
    window = _window(qtbot, tmp_path, missing)
    try:
        window.workflow.presets.setCurrentIndex(1)
        window.add_photos((source,))
        window.apply_coordinates(0, 0)
        window.output_edit.setText(str(tmp_path / "out"))
        window.start()
        qtbot.waitUntil(lambda: not window._busy, timeout=20000)
        assert window.results and window.results[0].status == ItemStatus.SUCCESS, (
            window.log.toPlainText()
        )
        target = tmp_path / "out/a.JPEG"
        with Image.open(target) as result:
            assert result.tobytes() == original_pixels
    finally:
        _close(qtbot, window)


def test_bad_row_blocks_whole_batch_and_identifies_photo(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources, tool: ExifTool
) -> None:
    first, second = tmp_path / "input/good.jpg", tmp_path / "input/bad.jpg"
    for path in (first, second):
        _photo(path)
    window = _window(qtbot, tmp_path, synthetic_watermark_resources)
    try:
        window.add_photos((first, second))
        window.model.setData(window.model.index(0, window.model.SUBJECT), "B-1356")
        window.output_edit.setText(str(tmp_path / "out"))
        window.start()
        qtbot.waitUntil(lambda: not window._busy, timeout=20000)
        assert not window.results
        assert "bad.jpg" in window.log.toPlainText()
        assert window.model.rows[1].status == "检查失败"
        assert window.model.rows[1].error
        assert not (tmp_path / "out").exists()
    finally:
        _close(qtbot, window)


def test_close_waits_for_cancelled_preflight_without_output(
    qtbot: QtBot,
    tmp_path: Path,
    synthetic_watermark_resources: WatermarkResources,
    tool: ExifTool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "input/a.jpg"
    _photo(source)
    started, release = Event(), Event()

    def slow_validate(*args: object) -> None:
        started.set()
        assert release.wait(10)

    monkeypatch.setattr(WatermarkStep, "validate", slow_validate)
    window = _window(qtbot, tmp_path, synthetic_watermark_resources)
    window.add_photos((source,))
    window.output_edit.setText(str(tmp_path / "out"))
    window.start()
    try:
        qtbot.waitUntil(started.is_set, timeout=10000)
        window.close()
        assert window._preflight_worker is not None
        assert window._preflight_worker.cancelled.is_set()
        assert window.isVisible()
    finally:
        release.set()
        _close(qtbot, window)
    assert not (tmp_path / "out").exists()


def test_nef_is_imported_but_watermark_is_blocked(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    source = tmp_path / "a.NEF"
    source.write_bytes(b"do not process")
    window = _window(qtbot, tmp_path, synthetic_watermark_resources)
    window.add_photos((source,))
    assert window.model.rowCount() == 1
    window._request_preview()
    assert window.preview.last_result is None
    assert "NEF 仅写入坐标" in window.preview.caption.text()
    window.output_edit.setText(str(tmp_path / "out"))
    window.start()
    assert "NEF 仅支持坐标写入" in window.log.toPlainText()
    assert not (tmp_path / "out").exists()
    _close(qtbot, window)
