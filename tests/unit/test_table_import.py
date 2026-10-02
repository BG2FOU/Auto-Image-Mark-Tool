"""S4 table parsing, row matching and apply-after-preview behavior."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904

from aim_tool.domain import PhotoItem
from aim_tool.services.table_import import (
    TableImportError,
    apply_import,
    apply_manual_date,
    preview_import,
    read_pasted_tsv,
    read_table,
)


def _photo(root: Path, relative: str, **kwargs: object) -> PhotoItem:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic photo")
    return PhotoItem(path, root, **kwargs)  # type: ignore[arg-type]


def test_bom_chinese_csv_preview_then_apply_without_overwriting_blank_cells(tmp_path: Path) -> None:
    root = tmp_path / "input"
    first = _photo(root, "子目录/甲.jpg", edits={"location_name": "原地点"})
    second = _photo(root, "乙.NEF", coordinates=(12.0, 34.0))
    table = tmp_path / "batch.csv"
    table.write_text(
        "文件名,类别,内容,拍摄日期,地点,纬度,经度\n"
        '子目录/甲.jpg,landscape,"海边,日出",2026-02-03T23:59:59,新地点,-24.5,118.25\n'
        "乙.NEF,,,,,,\n",
        encoding="utf-8-sig",
    )
    rows = read_table(table)
    preview = preview_import(rows, (first, second))
    assert preview.errors == ()
    assert [entry.photo_id for entry in preview.matches] == [first.id, second.id]
    assert first.taken_on is None
    updated_first, updated_second = apply_import(preview, (first, second))
    assert updated_first.id == first.id
    assert updated_first.edits["location_name"] == "新地点"
    assert updated_first.edits["category"] == "landscape"
    assert updated_first.edits["subject"] == "海边,日出"
    assert updated_first.taken_on == date(2026, 2, 3)
    assert updated_first.edits["capture_date_source"] == "table"
    assert updated_first.edits["capture_date_original"] == "2026-02-03T23:59:59"
    assert updated_first.coordinates == (-24.5, 118.25)
    assert updated_second.coordinates == (12.0, 34.0)
    assert first.edits == {"location_name": "原地点"}


def test_tsv_quotes_crlf_and_physical_error_line(tmp_path: Path) -> None:
    table = tmp_path / "batch.tsv"
    table.write_bytes(
        'file_name\tcategory\tsubject\r\n"a.jpg"\tlandscape\t"两行\n内容"\r\nmissing.jpg\tlandscape\t内容\r\n'.encode()
    )
    rows = read_table(table)
    assert rows[0].values["subject"] == "两行\n内容"
    assert rows[1].line == 4
    photo = _photo(tmp_path / "input", "a.jpg")
    preview = preview_import(rows, (photo,))
    assert preview.errors == (
        "Row 3: Missing or invalid watermark subject",
        "Row 4: no photo matches missing.jpg",
    )
    with pytest.raises(TableImportError, match="Resolve preview errors"):
        apply_import(preview, (photo,))


def test_duplicate_and_ambiguous_names_do_not_guess_by_row_order(tmp_path: Path) -> None:
    first = _photo(tmp_path / "a", "same.jpg")
    second = _photo(tmp_path / "b", "same.jpg")
    table = tmp_path / "batch.csv"
    table.write_text("file_name,latitude,longitude\nsame.jpg,1,2\n", encoding="utf-8")
    preview = preview_import(read_table(table), (first, second))
    assert preview.errors == ("Row 2: ambiguous photo same.jpg",)
    only_one = preview_import(read_table(table), (first,))
    assert only_one.errors == ()
    table.write_text("file_name\nsame.jpg\nsame.jpg\n", encoding="utf-8")
    duplicate = preview_import(read_table(table), (first,))
    assert duplicate.errors == ("Row 3: duplicate photo same.jpg",)


def test_reject_unsafe_paths_and_invalid_row_values(tmp_path: Path) -> None:
    photo = _photo(tmp_path / "input", "a.jpg")
    for row in (
        "../a.jpg,,,,,,",
        "a/./a.jpg,,,,,,",
        "a.jpg,railway,,,,,",
        "a.jpg,railway,B-123,2026-02-30,,,",
        "a.jpg,,,,,91,2",
        "a.jpg,,,,,1,",
    ):
        table = tmp_path / "batch.csv"
        table.write_text(
            f"file_name,category,subject,capture_date,location_name,latitude,longitude\n{row}\n",
            encoding="utf-8",
        )
        assert preview_import(read_table(table), (photo,)).errors


def test_xlsx_1904_date_sheet_selection_and_formula_rejection(tmp_path: Path) -> None:
    workbook = Workbook()
    workbook.epoch = CALENDAR_MAC_1904
    worksheet = workbook.active
    worksheet.title = "other"
    worksheet.append(("file_name", "capture_date"))
    excel_date = datetime(2024, 2, 29, 8, 9, 10)  # noqa: DTZ001 - Excel stores local dates
    worksheet.append(("wrong.jpg", excel_date))
    selected = workbook.create_sheet("selected")
    selected.append(("file_name", "capture_date"))
    selected.append(("a.jpg", excel_date))
    table = tmp_path / "batch.xlsx"
    workbook.save(table)
    rows = read_table(table, sheet="selected")
    assert rows[0].values["capture_date"] == excel_date
    photo = _photo(tmp_path / "input", "a.jpg")
    updated = apply_import(preview_import(rows, (photo,)), (photo,))
    assert updated[0].taken_on == date(2024, 2, 29)
    with pytest.raises(TableImportError, match="Unknown worksheet"):
        read_table(table, sheet="missing")
    selected["B2"] = "=TODAY()"
    workbook.save(table)
    with pytest.raises(TableImportError, match="Formula cell"):
        read_table(table, sheet="selected")
    selected["B2"] = "2024-02-29"
    selected["A2"] = 123
    workbook.save(table)
    with pytest.raises(TableImportError, match="must be text"):
        read_table(table, sheet="selected")


def test_encoding_is_explicit_and_duplicate_mapped_headers_fail(tmp_path: Path) -> None:
    table = tmp_path / "batch.csv"
    table.write_bytes("文件名,内容\n甲.jpg,山\n".encode("gb18030"))
    with pytest.raises(TableImportError, match="Cannot read table"):
        read_table(table)
    rows = read_table(table, encoding="gb18030")
    assert rows[0].values["file_name"] == "甲.jpg"
    table.write_text("文件名,file_name\na.jpg,a.jpg\n", encoding="utf-8")
    with pytest.raises(TableImportError, match="Duplicate mapped column"):
        read_table(table)


def test_pasted_tsv_uses_same_preview_and_validation(tmp_path: Path) -> None:
    photo = _photo(tmp_path / "input", "a.jpg")
    rows = read_pasted_tsv("文件名\t拍摄日期\r\na.jpg\t2026/02/03\r\n")
    preview = preview_import(rows, (photo,))
    assert preview.errors == ()
    assert apply_import(preview, (photo,))[0].taken_on == date(2026, 2, 3)


def test_manual_date_has_priority_over_table_date(tmp_path: Path) -> None:
    photo = apply_manual_date(_photo(tmp_path / "input", "a.jpg"), "2026/04/05")
    table = tmp_path / "batch.csv"
    table.write_text("file_name,capture_date\na.jpg,2026/03/04\n", encoding="utf-8")
    updated = apply_import(preview_import(read_table(table), (photo,)), (photo,))[0]
    assert updated.taken_on == date(2026, 4, 5)
    assert updated.edits["capture_date_source"] == "manual"
    assert updated.edits["imported_capture_date_original"] == "2026/03/04"
    with pytest.raises(ValueError, match="Invalid calendar"):
        apply_manual_date(photo, "2026/02/30")


def test_explicit_custom_headers_share_csv_and_clipboard_validation(tmp_path: Path) -> None:
    mapping = {"图片": "file_name", "注册号": "subject", "类型": "category"}
    text = "图片\t注册号\t类型\na.jpg\tB-1356\taviation\n"
    photo = _photo(tmp_path / "input", "a.jpg")
    rows = read_pasted_tsv(text, column_mapping=mapping)
    assert not preview_import(rows, (photo,)).errors
    table = tmp_path / "batch.csv"
    table.write_text(text.replace("\t", ","))
    assert read_table(table, column_mapping=mapping) == rows
    with pytest.raises(TableImportError, match="supported field"):
        read_pasted_tsv(text, column_mapping={"图片": "unknown"})
