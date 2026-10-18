"""Inclusive stage timings and simultaneous process-tree memory for local benchmarks."""

from __future__ import annotations

import ctypes
import functools
import os
import sys
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Self
from unittest.mock import patch


def process_memory() -> tuple[int, int | None]:
    """Sum current working sets, not unrelated high-water marks. Bytes, including children."""
    if sys.platform == "linux":
        pending = [os.getpid()]
        seen: set[int] = set()
        rss = 0
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        rss += int(line.split()[1]) * 1024
                for task in Path(f"/proc/{pid}/task").iterdir():
                    pending.extend(map(int, (task / "children").read_text().split()))
            except (OSError, ValueError):
                continue  # A child may exit between enumeration and sampling.
        return rss, None
    if sys.platform == "win32":
        from ctypes import wintypes as w

        class Entry(ctypes.Structure):
            _fields_ = [
                ("dwSize", w.DWORD),
                ("cntUsage", w.DWORD),
                ("pid", w.DWORD),
                ("heap", ctypes.c_size_t),
                ("module", w.DWORD),
                ("threads", w.DWORD),
                ("parent", w.DWORD),
                ("priority", w.LONG),
                ("flags", w.DWORD),
                ("exe", w.WCHAR * 260),
            ]

        class Counters(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_ws",
                    "working_set",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                    "private",
                )
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
        kernel.OpenProcess.restype = w.HANDLE
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Counters), w.DWORD]
        snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise OSError("Cannot enumerate process tree")
        parents = {}
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            valid = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while valid:
                parents[entry.pid] = entry.parent
                valid = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
        selected = {os.getpid()}
        while True:
            children = {pid for pid, parent in parents.items() if parent in selected}
            if children <= selected:
                break
            selected.update(children)
        rss = private = 0
        for pid in selected:
            handle = kernel.OpenProcess(0x410, False, pid)
            if not handle:
                if pid == os.getpid():
                    raise OSError("Cannot inspect benchmark process")
                continue
            try:
                counters = Counters()
                counters.cb = ctypes.sizeof(counters)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    rss += counters.working_set
                    private += counters.private
            finally:
                kernel.CloseHandle(handle)
        return rss, private
    raise OSError("Process-tree sampling is unavailable on this platform")


class Metrics:
    def __init__(self) -> None:
        self.phase = "setup"
        self.stages: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
        self.memory: dict[str, dict[str, float | None]] = {}
        self.memory_error: str | None = None
        self._lock = Lock()
        self._stop = Event()
        self._thread = Thread(target=self._sample, daemon=True)
        self._patches = ExitStack()

    def _sample(self) -> None:
        while not self._stop.is_set():
            try:
                rss, private = process_memory()
                with self._lock:
                    row = self.memory.setdefault(self.phase, {"rss_mib": 0.0, "private_mib": None})
                    row["rss_mib"] = max(row["rss_mib"] or 0, rss / 1024**2)
                    if private is not None:
                        row["private_mib"] = max(row["private_mib"] or 0, private / 1024**2)
            except OSError as error:
                self.memory_error = str(error)
                return
            self._stop.wait(0.025)

    def wrap(self, owner: object, name: str, label: str) -> None:
        original = getattr(owner, name)

        @functools.wraps(original)
        def timed(*args: object, **kwargs: object) -> object:
            phase = self.phase
            start = perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                with self._lock:
                    row = self.stages[phase].setdefault(label, {"calls": 0, "seconds": 0})
                    row["calls"] += 1
                    row["seconds"] += perf_counter() - start

        self._patches.enter_context(patch.object(owner, name, timed))

    def __enter__(self) -> Self:
        from PIL import ImageCms

        from aim_tool.services import frequency_watermark, images, watermark
        from aim_tool.services.exiftool import ExifTool
        from aim_tool.workflow import steps

        for owner, names in (
            (images, ("validate_jpeg", "prepare_jpeg", "_digest")),
            (ImageCms, ("buildTransform", "profileToProfile")),
            (watermark, ("render_watermark_region",)),
            (frequency_watermark, ("embed", "extract", "verify_signature", "luminance")),
            (steps, ("_sha256",)),
            (ExifTool, ("_run",)),
        ):
            for name in names:
                self.wrap(owner, name, f"{owner.__name__}.{name}")
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._thread.join()
        self._patches.close()
