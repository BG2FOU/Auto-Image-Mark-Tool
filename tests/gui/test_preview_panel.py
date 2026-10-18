"""Latest-only previews, real shared rendering and original-pixel dragging."""

from datetime import date
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from pytestqt.qtbot import QtBot

from aim_tool.domain import PhotoItem
from aim_tool.services.storage import WatermarkSettings
from aim_tool.services.watermark import WatermarkResources
from aim_tool.ui.preview_panel import PreviewPanel
from aim_tool.ui.workers import PreviewResult


def test_preview_reuses_base_across_parameters_without_accumulating_watermark(
    qtbot: QtBot,
    tmp_path: Path,
    synthetic_watermark_resources: WatermarkResources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aim_tool.services import images

    source = tmp_path / "base.jpg"
    Image.new("RGB", (1007, 672), (30, 50, 70)).save(source)
    photo = PhotoItem(
        source,
        tmp_path,
        taken_on=date(2026, 10, 18),
        edits={"category": "aviation", "subject": "B-1356"},
    )
    calls = 0
    original = images.prepare_jpeg

    def counted(path):
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(images, "prepare_jpeg", counted)
    panel = PreviewPanel()
    qtbot.addWidget(panel)
    try:
        panel.request(photo, WatermarkSettings(synthetic_watermark_resources))
        qtbot.waitUntil(lambda: not panel.busy, timeout=20000)
        panel.request(photo, None)
        qtbot.waitUntil(lambda: not panel.busy, timeout=20000)
        assert calls == 1 and panel.last_result is not None
        with Image.open(source) as expected:
            color = expected.getpixel((0, 0))
        result = panel.last_result.image
        assert result.pixelColor(1000, 665).getRgb()[:3] == color
        panel.invalidate("paused")
        panel.request(photo, None)
        qtbot.waitUntil(lambda: not panel.busy, timeout=20000)
        assert calls == 2
    finally:
        panel.shutdown()


def test_digital_preview_uses_selected_algorithm_level_and_original_size(
    qtbot: QtBot,
    tmp_path: Path,
    synthetic_watermark_resources: WatermarkResources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aim_tool.services import frequency_watermark as frequency

    captured = []

    def mark(pixels, config, signature, *, cancelled=None):
        captured.append((pixels.size, config.algorithm, config.level, signature, cancelled))
        return Image.new("RGB", pixels.size, (77, 88, 99))

    monkeypatch.setattr(frequency, "apply_signature", mark)
    source = tmp_path / "preview.jpg"
    Image.new("RGB", (1007, 672), (20, 40, 60)).save(source)
    photo = PhotoItem(
        source,
        tmp_path,
        taken_on=date(2026, 10, 13),
        edits={"category": "aviation", "subject": "B-1356"},
    )
    panel = PreviewPanel()
    qtbot.addWidget(panel)
    params = frequency.digital_defaults({"digital_algorithm": "fft", "digital_level": "high"})
    panel.request(photo, WatermarkSettings(synthetic_watermark_resources, params))
    qtbot.waitUntil(lambda: panel.last_result is not None, timeout=20000)
    assert captured[0][:4] == ((1007, 672), "fft", "high", synthetic_watermark_resources.signature)
    assert captured[0][4] is not None
    assert "FFT · 高档" in panel.caption.text()
    assert panel.last_result.image.pixelColor(0, 0).getRgb()[:3] == (77, 88, 99)
    panel.shutdown()


def test_stale_result_does_not_replace_current_photo(qtbot: QtBot) -> None:
    panel = PreviewPanel()
    qtbot.addWidget(panel)
    panel.generation = 2
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    old = PreviewResult(1, "old", image, image, (400, 300), None, "old", ())
    current = PreviewResult(2, "current", image, image, (400, 300), None, "current", ())
    panel.accept_result(current)
    panel.accept_result(old)
    assert panel.last_result == current
    assert panel.caption.text() == "current"


def test_async_preview_coalesces_and_matches_actual_geometry(
    qtbot: QtBot, tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    source = tmp_path / "a.jpg"
    Image.new("RGB", (1007, 672), (20, 40, 60)).save(source)
    photo = PhotoItem(
        source,
        tmp_path,
        taken_on=date(2026, 9, 26),
        edits={"category": "aviation", "subject": "B-1356"},
    )
    panel = PreviewPanel()
    qtbot.addWidget(panel)
    panel.resize(600, 550)
    panel.show()
    panel.request(photo, WatermarkSettings(synthetic_watermark_resources))
    panel.request(photo, WatermarkSettings(synthetic_watermark_resources, {"font_size_pt": 24}))
    qtbot.waitUntil(lambda: not panel.busy, timeout=20000)
    assert panel.last_result is not None, panel.caption.text()
    assert panel.last_result.generation == 2
    assert panel.last_result.size == (1007, 672)
    assert "字号 17 px" in panel.caption.text()
    assert panel.last_result.bounds is not None
    assert panel.last_result.size[0] - panel.last_result.bounds[2] == 4
    canvas = panel.canvas
    start = canvas.watermark_rect().center().toPoint()
    dx = -20
    expected = dx * 1007 / canvas.image_rect().width()
    with qtbot.waitSignal(panel.moved, timeout=2000) as signal:
        qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
        qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(dx, 0))
    assert abs(signal.args[0] - expected) < 0.01
    panel.shutdown()
