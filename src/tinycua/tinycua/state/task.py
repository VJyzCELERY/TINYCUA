"""Task and TaskList state objects."""

from __future__ import annotations

__all__ = ["Task", "TaskList"]

import dataclasses

from tinycua.state.base import StateObject


@dataclasses.dataclass
class Task(StateObject):
    """A single task in the execution plan.

    Attributes:
        task_id: Unique task identifier.
        name: Task name.
        description: Task description.
        context: Task-specific context in structured markdown.
        success_criteria: List of criteria for task completion.
        confidence: Agent-assigned confidence in decomposition or readiness.
        tasks: Optional nested sub-tasks. When present, this is a container task.
    """

    task_id: str
    name: str
    description: str
    context: str
    success_criteria: list[str]
    confidence: float
    tasks: list[Task] | None = None


@dataclasses.dataclass
class TaskList(StateObject):
    """A sequential roadmap of tasks with current position tracking.

    Attributes:
        tasks: List of Task objects (may be containers with nested tasks).
        current_task_id: ID of the currently active task.
    """

    tasks: list[Task]
    current_task_id: str | None = None
