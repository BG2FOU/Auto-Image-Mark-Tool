"""One content-bound preview base, independent of mutable rendering parameters."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Lock

from aim_tool.services import images
from aim_tool.services.file_state import FileState, file_state


class PreviewBaseCache:
    def __init__(self, max_bytes: int = 96 * 1024**2) -> None:
        self.max_bytes = max_bytes
        self._entry: tuple[Path, FileState, images.PreparedJpeg] | None = None
        self._generation = 0
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._entry = None
            self._generation += 1

    def prepare(self, path: Path, cancelled: Event | None = None) -> images.PreparedJpeg:
        path = path.resolve()
        state = file_state(path, cancelled)
        with self._lock:
            generation = self._generation
            cached = None
            if self._entry is not None and self._entry[:2] == (path, state):
                cached = self._entry[2]
            else:
                self._entry = None  # Release the previous photo before decoding another.
        prepared = cached if cached is not None else images.prepare_jpeg(path)
        retain = prepared.pixels.width * prepared.pixels.height * 4 <= self.max_bytes
        if file_state(path, cancelled) != state:
            raise OSError("Source changed while preparing preview")
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("预览已取消")
        with self._lock:
            if generation != self._generation:
                retain = False  # An invalidation while decoding must not repopulate the cache.
            elif retain:
                self._entry = path, state, prepared
        # Composition and thumbnail() both mutate pixels: never expose the retained base.
        pixels = prepared.pixels.copy() if retain or cached is not None else prepared.pixels
        return images.PreparedJpeg(pixels, prepared.srgb_icc, prepared.dpi, prepared.warnings)
