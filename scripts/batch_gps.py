"""Preview or execute a local CSV-selected GPS-only JPEG batch."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from io import TextIOWrapper
from pathlib import Path

from aim_tool.domain import BatchJob, ItemResult, ItemStatus, PhotoItem
from aim_tool.services.exiftool import ExifTool, validate_coordinates
from aim_tool.workflow.engine import build_plan, run_plan
from aim_tool.workflow.registry import StepRegistry, preset
from aim_tool.workflow.steps import ExportStep, LocationStep


def load_rows(table: Path, input_root: Path) -> tuple[PhotoItem, ...]:
    root = input_root.resolve()
    items: list[PhotoItem] = []
    seen: set[str] = set()
    with table.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not {"file_name", "latitude", "longitude"} <= set(
            reader.fieldnames
        ):
            raise ValueError("CSV requires file_name,latitude,longitude headers")
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(row.get(key) is None for key in reader.fieldnames):
                raise ValueError(f"Malformed CSV row {line_number}")
            name = row["file_name"].strip()
            if not name:
                raise ValueError(f"Missing file_name at row {line_number}")
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe file_name at row {line_number}")
            key = relative.as_posix().casefold()
            if key in seen:
                raise ValueError(f"Duplicate file_name at row {line_number}")
            seen.add(key)
            try:
                latitude = float(row["latitude"])
                longitude = float(row["longitude"])
            except ValueError as error:
                raise ValueError(f"Invalid coordinates at row {line_number}") from error
            validate_coordinates(latitude, longitude)
            items.append(
                PhotoItem(
                    root / relative,
                    root,
                    coordinates=(latitude, longitude),
                    altitude=float(row.get("altitude", "").strip() or "0"),
                )
            )
    if not items:
        raise ValueError("CSV has no photo rows")
    return tuple(items)


def _report(path: Path, results: tuple[ItemResult, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "photo_id": str(result.photo_id),
            "status": result.status.value,
            "output": str(result.output) if result.output else None,
            "step": result.current_step,
            "error": result.error,
            "warnings": list(result.warnings),
        }
        for result in results
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")
    if isinstance(sys.stderr, TextIOWrapper):
        sys.stderr.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", type=Path, required=True, help="UTF-8 CSV with exact relative paths"
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--exiftool", type=Path, help="Pinned ExifTool 13.59 executable")
    parser.add_argument("--clear-auxiliary-gps", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Write outputs after full preflight")
    parser.add_argument(
        "--report", type=Path, help="Local JSON result report; excludes coordinates"
    )
    args = parser.parse_args()

    try:
        tool = ExifTool(args.exiftool)
        rows = load_rows(args.csv, args.input_root)
        registry = StepRegistry()
        registry.register(LocationStep(tool, clear_auxiliary_gps=args.clear_auxiliary_gps))
        registry.register(ExportStep())
        plan = build_plan(
            BatchJob(rows, preset("location_only"), args.output_root),
            registry,
        )
        for item in plan.items:
            print(f"{item.photo.source.name} -> {item.target}")
        if not args.execute:
            print(f"Preflight passed for {len(plan.items)} files; add --execute to write copies.")
            return 0
        results = run_plan(plan)
        if args.report:
            _report(args.report, results)
        for result in results:
            status = result.status.value
            detail = str(result.output) if result.output else (result.error or "")
            print(f"{status}: {detail}")
        return 0 if all(result.status == ItemStatus.SUCCESS for result in results) else 1
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"Batch preflight failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
