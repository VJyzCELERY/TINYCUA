"""Task state models for TinyCUA worker execution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """Lifecycle status for a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ReviewerDecision(StrEnum):
    """Review decision for a task result."""

    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


@dataclass
class TaskResult:
    """Persisted result for a task execution."""

    content: str
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    """Aggregated worker-mode result."""

    summary: str
    task_results: list[TaskResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Session-local task tree node."""

    title: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    description: str = ""
    children: list[str] = field(default_factory=list)
    result: TaskResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskStateStore:
    """Simple in-memory task state store."""

    tasks: dict[str, Task] = field(default_factory=dict)
    root_task_id: str | None = None

    def create_task(
        self,
        title: str,
        *,
        parent_id: str | None = None,
        description: str = "",
    ) -> Task:
        """Create and store a task."""
        task = Task(title=title, parent_id=parent_id, description=description)
        self.tasks[task.task_id] = task
        if parent_id and parent_id in self.tasks:
            self.tasks[parent_id].children.append(task.task_id)
        if self.root_task_id is None:
            self.root_task_id = task.task_id
        return task
