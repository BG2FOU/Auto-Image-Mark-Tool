"""Content-bound file snapshots for short-lived, validated work."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from threading import Event


@dataclass(frozen=True)
class FileState:
    identity: tuple[int, int, int, int, int]
    digest: str


def file_state(path: Path, cancelled: Event | None = None) -> FileState:
    def identity() -> tuple[int, int, int, int, int]:
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    before = identity()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            if cancelled is not None and cancelled.is_set():
                raise InterruptedError("检查已取消")
            digest.update(block)
    if identity() != before:
        raise OSError("File changed while reading its content snapshot")
    return FileState(before, digest.hexdigest())
