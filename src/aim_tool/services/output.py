"""Output naming and path preflight; no source photo is written here."""

from __future__ import annotations

import os
from pathlib import Path

from aim_tool.domain import PhotoItem, WorkflowSpec


class OutputError(ValueError):
    """A source/target pair or destination set is unsafe."""


def output_path(photo: PhotoItem, workflow: WorkflowSpec, output_root: Path) -> Path:
    source = photo.source.resolve()
    root = photo.import_root.resolve()
    destination = output_root.resolve()
    try:
        relative = source.relative_to(root)
    except ValueError as error:
        raise OutputError(f"Source is outside its import root: {source}") from error
    suffix = source.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".nef"}:
        raise OutputError(f"Unsupported input: {source.name}")
    if not source.is_file():
        raise OutputError(f"Input is missing: {source}")
    marked = any(step.enabled and step.component_id == "watermark" for step in workflow.steps)
    if marked and source.stem.casefold().endswith("_marked"):
        raise OutputError(f"Already marked input: {source.name}")
    name = f"{source.stem}_marked.jpg" if marked else source.name
    target = (destination / relative.parent / name).resolve()
    if target == source or target.parent == source.parent:
        raise OutputError(f"Output directory must differ from source: {source.parent}")
    if target.exists() or target.is_symlink():
        raise OutputError(f"Output already exists: {target}")
    return target


def require_distinct_targets(targets: tuple[Path, ...]) -> None:
    seen: set[str] = set()
    for target in targets:
        key = os.path.normcase(str(target)).casefold()
        if key in seen:
            raise OutputError(f"Multiple inputs would write the same output: {target}")
        seen.add(key)


def commit_no_overwrite(temporary: Path, target: Path) -> None:
    """Atomically expose a completed same-volume file without replacing a target."""
    if temporary.resolve() == target.resolve():
        raise OutputError("Temporary and target paths must differ")
    if temporary.stat().st_dev != target.parent.stat().st_dev:
        raise OutputError("Temporary file must be on the target volume")
    os.link(temporary, target)
    temporary.unlink()
