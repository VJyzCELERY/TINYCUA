"""TaskResult state object."""

from __future__ import annotations

__all__ = ["TaskResult", "TaskStatus"]

import dataclasses
from typing import Literal

from tinycua.state.base import StateObject

TaskStatus = Literal["completed", "failed", "blocked"]


@dataclasses.dataclass
class TaskResult(StateObject):
    """Output of a single task execution.

    Attributes:
        task_id: ID of the executed task.
        status: Completion status - completed, failed, or blocked.
        result: Task execution result text.
        discovered_sequence_issues: Optional list of sequencing issues found.
        uncertainty_notes: Optional list of uncertainty notes.
    """

    task_id: str
    status: TaskStatus
    result: str
    discovered_sequence_issues: list[str] | None = None
    uncertainty_notes: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate status enum value."""
        self._validate_enum(
            self.status,
            {"completed", "failed", "blocked"},
            "status",
        )
