"""Offline frozen JPG checks using generated images, block glyphs and isolated settings."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from fontTools.fontBuilder import FontBuilder  # type: ignore[import-untyped]
from fontTools.pens.ttGlyphPen import TTGlyphPen  # type: ignore[import-untyped]
from openpyxl import Workbook  # type: ignore[import-untyped]
from PIL import Image, ImageCms
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QLabel

from aim_tool import __version__
from aim_tool.domain import BatchJob, ItemStatus, LocationPreset, PhotoItem
from aim_tool.services.exiftool import ExifTool
from aim_tool.services.nef_gps import fingerprint_nef
from aim_tool.services.storage import ConfigStore, WatermarkSettings, WatermarkSettingsStore
from aim_tool.services.table_import import read_table
from aim_tool.services.watermark import WatermarkResources
from aim_tool.ui.coordinate_converter import CoordinateConverterDialog
from aim_tool.ui.main_window import MainWindow
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep


def _resources(root: Path) -> WatermarkResources:
    font = root / "synthetic.ttf"
    cmap = {code: f"g{code}" for code in (*range(32, 127), 169)}
    order = [".notdef", *cmap.values()]
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        if name != "g32":
            pen.moveTo((30, 0))
            pen.lineTo((450, 0))
            pen.lineTo((450, 700))
            pen.lineTo((30, 700))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (500, 0) for name in order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "AIM Synthetic", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.save(font)
    signature = root / "synthetic.png"
    Image.new("RGBA", (30, 18), (240, 240, 240, 255)).save(signature)
    return WatermarkResources(font, font, signature)


def _wait(predicate: Callable[[], bool], timeout: float = 60) -> None:
    loop = QEventLoop()
    timer = QTimer()
    deadline = monotonic() + timeout

    def poll() -> None:
        if predicate() or monotonic() >= deadline:
            loop.quit()

    timer.timeout.connect(poll)
    timer.start(20)
    if not predicate():
        loop.exec()
    timer.stop()
    if not predicate():
        raise TimeoutError("JPG self-test worker did not finish")


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _add_editing_lists(source: Path) -> None:
    """Exercise repeated mask and document-history limits with our own tiny XMP."""
    items = "<rdf:li>0</rdf:li>" * 1001
    mask = (
        '<rdf:li rdf:parseType="Resource"><crs:GestureDabs><rdf:Seq>'
        f"{items}</rdf:Seq></crs:GestureDabs></rdf:li>"
    )
    xml = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"'
        ' xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">'
        '<crs:MaskGroupBasedCorrections><rdf:Seq><rdf:li rdf:parseType="Resource">'
        f"<crs:CorrectionMasks><rdf:Seq>{mask * 2}</rdf:Seq></crs:CorrectionMasks>"
        "</rdf:li></rdf:Seq></crs:MaskGroupBasedCorrections>"
        f"<photoshop:DocumentAncestors><rdf:Bag>{items}</rdf:Bag></photoshop:DocumentAncestors>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    packet = b"http://ns.adobe.com/xap/1.0/\0" + xml.encode("utf-8")
    jpeg = source.read_bytes()
    source.write_bytes(
        jpeg[:2] + b"\xff\xe1" + (len(packet) + 2).to_bytes(2, "big") + packet + jpeg[2:]
    )


def run_self_test(report: Path) -> int:
    result: dict[str, object] = {
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "ok": False,
    }
    try:
        application = QApplication.instance() or QApplication([])
        if not isinstance(application, QApplication):
            raise TypeError("A QApplication is required")
        application.setQuitOnLastWindowClosed(False)
        with TemporaryDirectory(prefix="aim-jpg-smoke-") as name:
            root = Path(name).resolve()
            source = root / "中文 路径" / "甲.jpg"
            source.parent.mkdir()
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            exif = Image.Exif()
            exif[274] = 6
            exif[34665] = {36867: "2026:09:26 15:33:31"}
            Image.new("RGB", (1007, 672), (30, 50, 70)).save(source, exif=exif, icc_profile=profile)
            _add_editing_lists(source)
            original = sha256(source.read_bytes()).digest()
            tool = ExifTool(timeout=30)
            if result["frozen"]:
                bundle = Path(getattr(sys, "_MEIPASS", "")).resolve()
                _check(tool.executable.is_relative_to(bundle), "ExifTool is not bundled")
            settings = WatermarkSettingsStore(root / "settings.json")
            expected_settings = WatermarkSettings(_resources(root))
            settings.save(expected_settings)
            _check(settings.load() == expected_settings, "Settings cannot be reopened")
            locations = ConfigStore(root / "locations.json")
            window = MainWindow(
                settings_store=settings,
                location_store=locations,
                workflow_store=ConfigStore(root / "workflows.json"),
            )
            try:
                window.show()
                application.processEvents()
                _check(window.isVisible(), "JPG window did not open")
                _check(
                    window.workflow.presets.currentData() == "location"
                    and window.workflow.location.isChecked()
                    and not window.workflow.watermark.isChecked(),
                    "Default workflow is not coordinates only",
                )
                window.resize(1100, 720)
                window.log.show()
                panel = window.workflow
                _wait(
                    lambda: (
                        panel.location.font().pixelSize() == 12
                        and panel.scroll_area.verticalScrollBar().maximum() > 0
                    ),
                    timeout=5,
                )
                for label in panel.content.findChildren(QLabel):
                    _check(
                        label.height() >= label.heightForWidth(label.width())
                        and label.font().pixelSize() >= 11,
                        "Workflow text is clipped in a small window with the log open",
                    )
                _check(
                    panel.location.height() >= panel.location.minimumSizeHint().height()
                    and panel.watermark.height() >= panel.watermark.minimumSizeHint().height(),
                    "Workflow controls are compressed",
                )
                window.log.hide()
                window.resize(1440, 1000)
                _wait(
                    lambda: (
                        panel.location.font().pixelSize() == 13
                        and panel.scroll_area.verticalScrollBar().maximum() == 0
                    ),
                    timeout=5,
                )
                window.location_panel.save_location(
                    LocationPreset("Smoke", -24.2, 118.4, altitude=125.5)
                )
                _check(
                    len(locations.load().locations) == 1
                    and locations.load().locations[0].altitude == 125.5,
                    "Location preset altitude was not saved",
                )
                window.add_photos((source,))
                window.workflow.presets.setCurrentIndex(2)
                window.bulk_subject.setText("B-1356")
                window.bulk_date.setText("2026/9/26")
                window.apply_fields_button.click()
                window.apply_coordinates(-24.2, 118.4, -12.5)
                window.output_edit.setText(str(root / "output"))
                _wait(lambda: window.preview.last_result is not None)
                preview = window.preview.last_result
                _check(
                    preview is not None and preview.bounds is not None, "Watermark preview failed"
                )
                window.start()
                _wait(lambda: not window._busy)
                _check(
                    len(window.results) == 1 and window.results[0].status == ItemStatus.SUCCESS,
                    window.log.toPlainText(),
                )
                output = root / "output" / "甲_marked.jpg"
                gps = tool.read_gps(output)
                _check(
                    gps is not None
                    and abs(gps.latitude + 24.2) <= 1e-6
                    and abs(gps.longitude - 118.4) <= 1e-6
                    and abs(gps.altitude + 12.5) <= 1e-4,
                    "GPS readback failed",
                )
                _check(
                    tool.metadata(output)["ExifIFD:DateTimeOriginal"] == "2026:09:26 15:33:31",
                    "Capture date changed",
                )
                _check(
                    not any(
                        key.startswith(("XMP-crs:", "XMP-photoshop:"))
                        for key in tool.metadata(output)
                    ),
                    "Unused editing lists leaked into the output",
                )
                with Image.open(output) as image:
                    _check(image.size == (672, 1007), "Orientation or dimensions failed")
                    _check(image.getexif().get(274) == 1, "Output orientation is not normalized")
                    _check(bool(image.info.get("icc_profile")), "Output ICC is missing")
                    _check(
                        preview is not None
                        and preview.bounds is not None
                        and max(image.crop(preview.bounds).convert("L").tobytes()) > 120,
                        "Watermark pixels did not change",
                    )
                _check(sha256(source.read_bytes()).digest() == original, "Source changed")
                _check(not list((root / "output").glob(".aim-*")), "Scratch files remain")
                window.save_report(root / "job.json")
                _check(json.loads((root / "job.json").read_text(encoding="utf-8")), "Empty report")
                workbook = Workbook()
                workbook.active.append(["文件名", "内容"])
                workbook.active.append(["甲.jpg", "B-1356"])
                workbook.save(root / "batch.xlsx")
                _check(
                    read_table(root / "batch.xlsx")[0].values["subject"] == "B-1356", "XLSX failed"
                )
                converted_store = ConfigStore(root / "converted-locations.json")
                converter = CoordinateConverterDialog(converted_store, window)
                converter.show()
                converter.input.setPlainText(
                    "name,latitude,longitude,altitude,coordinate_system\n"
                    "PublicTest,39.91334545536069,116.38404722455657,-12.5,GCJ-02\n"
                )
                converter.convert_button.click()
                _wait(lambda: converter._worker is None)
                _check(converter.save_button.isEnabled(), "Coordinate conversion preview failed")
                converter.save_button.click()
                converted_location = converted_store.load().locations[0]
                _check(
                    abs(converted_location.latitude - 39.911954) < 2e-7
                    and abs(converted_location.longitude - 116.377817) < 2e-7
                    and converted_location.altitude == -12.5,
                    "Converted location or altitude was not saved",
                )
                converter.close()
                # A renamed synthetic JPEG is deliberately NOT a valid supported NEF.
                # Test packaging and rejection; this does not certify a real camera file.
                invalid_nef = root / "unsupported.NEF"
                invalid_nef.write_bytes(source.read_bytes())
                try:
                    fingerprint_nef(tool, invalid_nef)
                except ValueError:
                    pass
                else:
                    raise RuntimeError("Renamed JPEG was accepted as RAW")
                nef = root / "synthetic.NEF"
                Image.new("RGB", (30, 20), (12, 34, 56)).save(nef, format="TIFF")
                tool._run_for_path(
                    nef,
                    "-overwrite_original",
                    "-IFD0:Make=NIKON CORPORATION",
                    "-IFD0:Model=NIKON ANY MODEL",
                    "-ExifIFD:DateTimeOriginal=2026:01:01 04:43:20",
                    "-ExifIFD:OffsetTimeOriginal=+08:00",
                )
                nef_source_hash = sha256(nef.read_bytes()).digest()
                nef_before = fingerprint_nef(tool, nef)
                registry = StepRegistry()
                registry.register(LocationStep(tool, allow_nef_after_viewer_check=True))
                registry.register(ExportStep())
                (nef_result,) = run_plan(
                    build_plan(
                        BatchJob(
                            (PhotoItem(nef, root, coordinates=(1, 2)),),
                            preset("location_only"),
                            root / "raw-output",
                        ),
                        registry,
                    )
                )
                _check(nef_result.output is not None, nef_result.error or "NEF output missing")
                nef_output = root / "raw-output/synthetic.NEF"
                gps_tags = tool.metadata(nef_output, "-GPS:all")
                _check(
                    fingerprint_nef(tool, nef_output).preserved_from(nef_before)
                    and sha256(nef.read_bytes()).digest() == nef_source_hash
                    and gps_tags.get("GPS:GPSSatellites") == "00"
                    and gps_tags.get("GPS:GPSMapDatum") == "WGS-84"
                    and gps_tags.get("GPS:GPSDateStamp") == "2025:12:31"
                    and gps_tags.get("GPS:GPSTimeStamp") == "20:43:20",
                    "RAW GPS metadata or preservation failed",
                )
                window.add_photos((invalid_nef,))
                window.table.selectRow(window.model.rowCount() - 1)
                window._request_preview()
                _check(
                    window.preview.last_result is None
                    and "NEF 仅写入坐标" in window.preview.caption.text(),
                    "NEF unexpectedly decoded a JPG preview",
                )
                window.start()
                _check(
                    not window._busy and "NEF 仅支持坐标写入" in window.log.toPlainText(),
                    "NEF watermark batch was not blocked",
                )
                _check(
                    not (root / "output/unsupported_marked.jpg").exists(), "NEF converted to JPG"
                )
                _check("rawpy" not in sys.modules, "GPS workflow imported RAW development")
            finally:
                window.close()
                _wait(lambda: not window.has_active_workers)
                window.close()
            result.update(
                ok=True,
                exiftool="13.59",
                checks=[
                    "gui",
                    "default_location",
                    "workflow_layout",
                    "nef_gps",
                    "settings",
                    "locations",
                    "preview",
                    "gps_watermark",
                    "orientation",
                    "icc",
                    "capture_date",
                    "source_unchanged",
                    "cleanup",
                    "report",
                    "xlsx",
                    "nef_scope",
                    "altitude",
                    "coordinate_conversion",
                    "editing_list_warnings",
                ],
            )
    except Exception as error:  # noqa: BLE001 - windowless builds report all smoke failures
        result["error"] = str(error)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1
