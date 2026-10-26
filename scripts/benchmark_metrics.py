"""Inclusive stage timings and simultaneous process-tree memory for local benchmarks."""

from __future__ import annotations

import ctypes
import functools
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Lock, Thread, get_ident, local
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
    def __init__(
        self, *, source_paths: Iterable[Path] = (), asset_paths: Iterable[Path] = ()
    ) -> None:
        self.phase = "setup"
        self.stages: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
        self.memory: dict[str, dict[str, float | None]] = {}
        self.memory_error: str | None = None
        self.photo_seconds: list[float] = []
        self.digest_reads: dict[str, dict[str, dict[str, dict[str, float]]]] = defaultdict(dict)
        self.preflight_seconds: dict[str, float] = defaultdict(float)
        self.execution_seconds = 0.0
        self.milestones: dict[str, float] = {}
        self.first_preparation_photo_id: str | None = None
        self.configured_workers: list[int] = []
        self.peak_active_items = 0
        self._source_paths = {path.resolve() for path in source_paths}
        self._asset_paths = {path.resolve() for path in asset_paths}
        self._active_items: set[object] = set()
        self._thread_items: dict[int, object] = {}
        self._plan_calls = 0
        self._action_started: float | None = None
        self._first_preparation_key: object | None = None
        self._phase_context = local()
        self._lock = Lock()
        self._stop = Event()
        self._thread = Thread(target=self._sample, daemon=True)
        self._patches = ExitStack()

    def begin_action(self, phase: str) -> None:
        """Start the clock immediately before a measured click or pipeline execution."""
        with self._lock:
            self.phase = phase
            self._action_started = perf_counter()
            self._first_preparation_key = None
            self.first_preparation_photo_id = None
            self.milestones.clear()

    def _current_phase(self) -> str:
        return getattr(self._phase_context, "phase", self.phase)

    def _restore_phase(self, previous: str | None) -> None:
        if previous is None:
            del self._phase_context.phase
        else:
            self._phase_context.phase = previous

    def mark(self, name: str, *, first: bool = True) -> None:
        now = perf_counter()
        with self._lock:
            if self._action_started is not None and (not first or name not in self.milestones):
                self.milestones[name] = now - self._action_started

    def _patch_aliases(self, owner: object, name: str, replacement: object) -> None:
        """Cover `from ... import ...` references already bound by application modules."""
        original = getattr(owner, name)
        references = [(owner, name)]
        for module in tuple(sys.modules.values()):
            module_name = getattr(module, "__name__", "")
            module_file = getattr(module, "__file__", "") or ""
            if not module_name.startswith("aim_tool.") and Path(module_file).name != (
                "benchmark_pipeline.py"
            ):
                continue
            for alias, value in tuple(vars(module).items()):
                if value is original and (module is not owner or alias != name):
                    references.append((module, alias))
        for module, alias in references:
            self._patches.enter_context(patch.object(module, alias, replacement))

    def _path_category(self, path: Path) -> str:
        resolved = path.resolve()
        if resolved in self._source_paths:
            return "original_source"
        if resolved in self._asset_paths:
            return "asset"
        return "artifact_or_other"

    def _item_started(self, key: object) -> None:
        now = perf_counter()
        with self._lock:
            previous = self._thread_items.get(get_ident())
            if previous is not None and previous != key:
                self._active_items.discard(previous)
            self._thread_items[get_ident()] = key
            self._active_items.add(key)
            self.peak_active_items = max(self.peak_active_items, len(self._active_items))
            if self._action_started is not None and self._first_preparation_key is None:
                self._first_preparation_key = key
                self.first_preparation_photo_id = str(key)
                elapsed = now - self._action_started
                self.milestones["first_item_execution_started_seconds"] = elapsed
                self.milestones["first_item_preparation_started_seconds"] = elapsed

    def _preparation_finished(self, key: object, *, complete: bool) -> None:
        now = perf_counter()
        with self._lock:
            if key != self._first_preparation_key or self._action_started is None:
                return
            elapsed = now - self._action_started
            if complete:
                finish = self.milestones.setdefault(
                    "first_item_preparation_finished_seconds", elapsed
                )
                self.milestones["first_item_preparation_duration_seconds"] = (
                    finish - self.milestones["first_item_preparation_started_seconds"]
                )
            else:
                self.milestones.setdefault("first_component_preparation_finished_seconds", elapsed)

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

    def wrap(
        self,
        owner: object,
        name: str,
        label: str,
        *,
        digest: bool = False,
        phase_scope: bool = False,
    ) -> None:
        original = getattr(owner, name)

        @functools.wraps(original)
        def timed(*args: object, **kwargs: object) -> object:
            phase = self._current_phase()
            previous_phase = getattr(self._phase_context, "phase", None)
            if phase_scope:
                self._phase_context.phase = phase
            category = None
            logical_bytes = 0
            if digest:
                path = Path(args[0])  # type: ignore[arg-type]
                category = self._path_category(path)
                try:
                    logical_bytes = path.stat().st_size
                except OSError:
                    pass
            start = perf_counter()
            succeeded = False
            try:
                result = original(*args, **kwargs)
                succeeded = True
                return result
            finally:
                elapsed = perf_counter() - start
                with self._lock:
                    row = self.stages[phase].setdefault(label, {"calls": 0, "seconds": 0})
                    row["calls"] += 1
                    row["seconds"] += elapsed
                    if category is not None:
                        rows = self.digest_reads[phase].setdefault(category, {})
                        reads = rows.setdefault(
                            label,
                            {"calls": 0, "successful_calls": 0, "logical_bytes": 0, "seconds": 0},
                        )
                        reads["calls"] += 1
                        reads["seconds"] += elapsed
                        if succeeded:
                            reads["successful_calls"] += 1
                            reads["logical_bytes"] += logical_bytes
                if phase_scope:
                    self._restore_phase(previous_phase)

        self._patch_aliases(owner, name, timed)

    def _wrap_step(self, owner: object, name: str) -> None:
        original = getattr(owner, name)

        @functools.wraps(original)
        def timed(step, item, spec, context):
            # prepare receives PhotoItem; execute receives Artifact. Both carry a
            # context.photo on production paths, which identifies the same task.
            photo = context.photo
            key = photo.id if photo is not None else id(context)
            self._item_started(key)
            start = perf_counter()
            succeeded = False
            phase = self._current_phase()
            try:
                result = original(step, item, spec, context)
                succeeded = True
                if name == "prepare":
                    self._preparation_finished(key, complete=False)
                if getattr(step, "id", None) == "export" and name == "execute":
                    self.mark("first_output_committed_seconds")
                return result
            finally:
                with self._lock:
                    row = self.stages[phase].setdefault(
                        f"{owner.__module__}.{owner.__name__}.{name}",
                        {"calls": 0, "seconds": 0},
                    )
                    row["calls"] += 1
                    row["seconds"] += perf_counter() - start
                    if not succeeded or getattr(step, "id", None) == "export":
                        self._active_items.discard(key)

        self._patches.enter_context(patch.object(owner, name, timed))

    def __enter__(self) -> Self:
        from PIL import ImageCms

        from aim_tool.services import file_state, frequency_watermark, images, nef_gps, watermark
        from aim_tool.services.exiftool import ExifTool
        from aim_tool.ui.workers import PreflightWorker
        from aim_tool.workflow import engine, steps

        original_build = engine.build_plan

        @functools.wraps(original_build)
        def timed_build(*args, **kwargs):
            phase = self._current_phase()
            start = perf_counter()
            try:
                return original_build(*args, **kwargs)
            finally:
                elapsed = perf_counter() - start
                with self._lock:
                    self.preflight_seconds[phase] += elapsed
                    row = self.stages[phase].setdefault(
                        "aim_tool.workflow.engine.build_plan", {"calls": 0, "seconds": 0}
                    )
                    row["calls"] += 1
                    row["seconds"] += elapsed

        self._patch_aliases(engine, "build_plan", timed_build)
        original_plan = engine.run_plan

        @functools.wraps(original_plan)
        def timed_item(plan, cancelled=None, progress=None, *, workers=1):
            with self._lock:
                outermost = self._plan_calls == 0
                self._plan_calls += 1
                if outermost:
                    self.configured_workers.append(min(workers, max(1, len(plan.items))))
            self.phase = "execution"
            previous_phase = getattr(self._phase_context, "phase", None)
            self._phase_context.phase = "execution"

            def measured_progress(photo, message):
                if message == "Preparing current source":
                    self._item_started(photo.id)
                elif message == "Prepared current source":
                    self._preparation_finished(photo.id, complete=True)
                if progress is not None:
                    progress(photo, message)

            start = perf_counter()
            try:
                return original_plan(plan, cancelled, measured_progress, workers=workers)
            finally:
                elapsed = perf_counter() - start
                with self._lock:
                    if len(plan.items) == 1:
                        self.photo_seconds.append(perf_counter() - start)
                        self._active_items.discard(plan.items[0].photo.id)
                    self._plan_calls -= 1
                    if outermost:
                        self.execution_seconds += elapsed
                        self._active_items.clear()
                        self._thread_items.clear()
                if outermost:
                    self.mark("core_batch_completed_seconds", first=False)
                self._restore_phase(previous_phase)

        self._patch_aliases(engine, "run_plan", timed_item)

        for owner, names in (
            (images, ("validate_jpeg", "prepare_jpeg")),
            (ImageCms, ("buildTransform", "profileToProfile")),
            (watermark, ("render_watermark_region",)),
            (frequency_watermark, ("embed", "extract", "verify_signature", "luminance")),
            (nef_gps, ("fingerprint_nef", "raw_diagnostics")),
            (ExifTool, ("_run",)),
        ):
            for name in names:
                self.wrap(owner, name, f"{owner.__name__}.{name}")
        self.wrap(PreflightWorker, "run", "PreflightWorker.run", phase_scope=True)
        for owner, name in ((file_state, "file_state"), (steps, "_sha256"), (images, "_digest")):
            self.wrap(owner, name, f"{owner.__name__}.{name}", digest=True)
        for owner in (steps.LocationStep, steps.WatermarkStep, steps.ExportStep):
            for name in ("prepare", "execute"):
                if hasattr(owner, name):
                    self._wrap_step(owner, name)
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._thread.join()
        self._patches.close()
