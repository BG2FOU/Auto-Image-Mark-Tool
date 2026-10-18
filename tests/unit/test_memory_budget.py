"""Admission uses the worst concurrent pair, reserves headroom and falls back to serial."""

from aim_tool.services import memory_budget

MIB = 1024**2


def test_two_workers_require_room_for_largest_pair_and_reserve() -> None:
    assert memory_budget.admitted_workers([100 * MIB] * 3, 2048 * MIB) == 2
    assert memory_budget.admitted_workers([100 * MIB] * 3, 512 * MIB) == 1
    assert memory_budget.admitted_workers([10 * MIB, 700 * MIB, 700 * MIB], 2048 * MIB) == 2
    assert memory_budget.admitted_workers([10 * MIB, 800 * MIB, 800 * MIB], 2048 * MIB) == 1
    assert memory_budget.admitted_workers([17_000_000 * 24 + 128 * MIB] * 2, 3072 * MIB) == 2
    assert memory_budget.admitted_workers([60_000_000 * 24 + 128 * MIB] * 2, 3072 * MIB) == 1


def test_unknown_memory_or_task_budget_stays_serial(monkeypatch) -> None:
    monkeypatch.setattr(memory_budget, "available_memory", lambda: None)
    assert memory_budget.admitted_workers([MIB, MIB]) == 1
    assert memory_budget.admitted_workers([MIB, None], 4096 * MIB) == 1
    assert memory_budget.admitted_workers([MIB], 4096 * MIB) == 1
    assert memory_budget.admitted_workers([0, MIB], 4096 * MIB) == 1
