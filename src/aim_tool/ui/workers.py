"""Qt signal bridge for preflighted GPS and watermark batch jobs."""

from __future__ import annotations

from threading import Event

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from aim_tool.workflow.engine import ExecutionPlan, run_plan


class BatchWorker(QThread):
    progress = Signal(str, str)
    completed = Signal(object)

    def __init__(self, plan: ExecutionPlan, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.cancelled = Event()

    def run(self) -> None:
        results = run_plan(
            self.plan,
            cancelled=self.cancelled,
            progress=lambda photo, message: self.progress.emit(str(photo.id), message),
        )
        self.completed.emit(results)
