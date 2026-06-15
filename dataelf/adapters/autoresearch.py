from __future__ import annotations

from typing import Protocol

from dataelf.schemas import TaskState


class AutoResearchAdapter(Protocol):
    def run(self, task_state: TaskState) -> TaskState:
        ...
