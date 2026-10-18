"""Preview bases are content-bound, bounded, cancellable and never mutated by a caller."""

import os
from pathlib import Path
from threading import Event

import pytest
from PIL import Image

from aim_tool.services import images
from aim_tool.services.preview_base import PreviewBaseCache


def test_preview_base_returns_owned_pixels_and_reloads_changed_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "a.jpg"
    Image.new("RGB", (120, 80), (20, 40, 60)).save(path)
    cache = PreviewBaseCache()
    count = 0
    original = images.prepare_jpeg

    def counted(source):
        nonlocal count
        count += 1
        return original(source)

    monkeypatch.setattr(images, "prepare_jpeg", counted)
    first = cache.prepare(path)
    expected = first.pixels.tobytes()
    first.pixels.paste((255, 255, 255), (0, 0, 120, 80))
    first.pixels.thumbnail((20, 20))
    second = cache.prepare(path)
    assert second.pixels.size == (120, 80) and second.pixels.tobytes() == expected
    assert count == 1
    stamp = path.stat()
    Image.new("RGB", (120, 80), (60, 40, 20)).save(path)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert cache.prepare(path).pixels.tobytes() != expected
    assert count == 2
    cache.clear()
    cache.prepare(path)
    assert count == 3


@pytest.mark.parametrize("invalidate", ["budget", "clear_during_decode", "cancel"])
def test_preview_base_does_not_retain_ineligible_or_cancelled_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalidate: str,
) -> None:
    path = tmp_path / "a.jpg"
    Image.new("RGB", (120, 80)).save(path)
    cache = PreviewBaseCache(max_bytes=1 if invalidate == "budget" else 1024**2)
    stop = Event()
    original = images.prepare_jpeg
    calls = 0

    def preparing(source):
        nonlocal calls
        calls += 1
        prepared = original(source)
        if calls == 1 and invalidate == "clear_during_decode":
            cache.clear()
        if calls == 1 and invalidate == "cancel":
            stop.set()
        return prepared

    monkeypatch.setattr(images, "prepare_jpeg", preparing)
    if invalidate == "cancel":
        with pytest.raises(InterruptedError):
            cache.prepare(path, stop)
    else:
        cache.prepare(path)
    stop.clear()
    cache.prepare(path, stop)
    assert calls == 2
