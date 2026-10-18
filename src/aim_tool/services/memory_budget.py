"""Conservative admission for at most two image tasks, with serial fallback."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Sequence
from pathlib import Path


def available_memory() -> int | None:
    try:
        if sys.platform == "linux":
            available = next(
                int(line.split()[1]) * 1024
                for line in Path("/proc/meminfo").read_text().splitlines()
                if line.startswith("MemAvailable:")
            )
            limit_path = Path("/sys/fs/cgroup/memory.max")
            if limit_path.exists():
                limit = limit_path.read_text().strip()
                if limit != "max":
                    current = int(Path("/sys/fs/cgroup/memory.current").read_text())
                    available = min(available, max(0, int(limit) - current))
            return available
        if sys.platform == "win32":

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong)
                    for name in (
                        "total_phys",
                        "avail_phys",
                        "total_commit",
                        "avail_commit",
                        "total_virtual",
                        "avail_virtual",
                        "extended",
                    )
                ]

            status = Status()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(min(status.avail_phys, status.avail_commit))
    except (OSError, ValueError, StopIteration):
        return None
    return None


def admitted_workers(estimates: Sequence[int | None], available: int | None = None) -> int:
    if len(estimates) < 2 or any(value is None or value <= 0 for value in estimates):
        return 1
    free = available_memory() if available is None else available
    if free is None or free <= 0:
        return 1
    largest = sorted(value for value in estimates if value is not None)[-2:]
    reserve = max(512 * 1024**2, free // 4)
    return 2 if sum(largest) + reserve <= free else 1
