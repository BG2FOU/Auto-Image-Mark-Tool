"""Latest-only previews, real shared rendering and original-pixel dragging."""

from datetime import date
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from pytestqt.qtbot import QtBot

from aim_tool.domain import PhotoItem
from aim_tool.services.storage import WatermarkSettings
from aim_tool.services.watermark import WatermarkResources
from aim_tool.ui.preview_panel import PreviewPanel
from aim_tool.ui.workers import PreviewResult


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
