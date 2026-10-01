"""Offline frozen-app smoke using only temporary synthetic JPEGs."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from aim_tool import __version__
from aim_tool.app import create_main_window
from aim_tool.domain import BatchJob, ItemStatus, PhotoItem
from aim_tool.services.exiftool import ExifTool
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep


def run_self_test(report: Path) -> int:
    application = QApplication.instance() or QApplication([])
    window = create_main_window()
    window.show()
    application.processEvents()
    if not window.isVisible():
        raise RuntimeError("GPS window failed to open")
    window.close()
    with TemporaryDirectory(prefix="aim-gps-gui-self-test-") as name:
        root = Path(name)
        input_root = root / "中文 路径"
        input_root.mkdir()
        source = input_root / "甲.jpg"
        picture = QImage(40, 30, QImage.Format.Format_RGB32)
        picture.fill(Qt.GlobalColor.blue)
        # PySide6 6.11 accepts str here even though its type stub declares bytes.
        if not picture.save(str(source), "JPEG"):  # type: ignore[call-overload]
            raise RuntimeError("Qt could not create a JPEG")
        before = sha256(source.read_bytes()).digest()
        tool = ExifTool()
        item = PhotoItem(source, input_root, coordinates=(-24.123456789, 118.987654321))
        registry = StepRegistry()
        registry.register(LocationStep(tool))
        registry.register(ExportStep())
        plan = build_plan(BatchJob((item,), preset("location_only"), root / "output"), registry)
        results = run_plan(plan)
        if (
            len(results) != 1
            or results[0].status != ItemStatus.SUCCESS
            or results[0].output is None
        ):
            raise RuntimeError("GPS batch self-test failed")
        output = results[0].output
        gps = tool.read_gps(output)
        if (
            gps is None
            or abs(gps.latitude + 24.123456789) > 1e-6
            or abs(gps.longitude - 118.987654321) > 1e-6
        ):
            raise RuntimeError("GPS readback failed")
        if sha256(source.read_bytes()).digest() != before:
            raise RuntimeError("Synthetic source changed")
        original_pixels = QImage(str(source))
        exported_pixels = QImage(str(output))
        if (
            original_pixels.isNull()
            or exported_pixels.isNull()
            or original_pixels.size() != exported_pixels.size()
        ):
            raise RuntimeError("JPEG decode failed")
        for y in range(original_pixels.height()):
            for x in range(original_pixels.width()):
                if original_pixels.pixel(x, y) != exported_pixels.pixel(x, y):
                    raise RuntimeError("JPEG pixels changed")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "version": __version__,
                "gui_started": True,
                "exiftool": "13.59",
                "gps_roundtrip": True,
                "source_unchanged": True,
                "pixels_unchanged": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0
