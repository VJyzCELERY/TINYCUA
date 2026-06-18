"""Task state models for TinyCUA worker execution."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, ClassVar


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
    REPLAN = "replan"
    OPEN_QUESTION = "open_question"


@dataclass
class TaskResult:
    """Persisted result for a task execution."""

    content: str
    task_id: str | None = None
    execution_status: str = "succeeded"
    reviewer_decision: str | None = None
    summary: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Keep legacy content and design summary fields aligned."""
        if not self.summary:
            self.summary = self.content


@dataclass
class WorkerResult:
    """Aggregated worker-mode result."""

    summary: str
    task_results: list[TaskResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedResult:
    """Response-ready aggregation of a completed worker task tree."""

    root_task_id: str
    task_summaries: list[str] = field(default_factory=list)
    accepted_results: list[TaskResult] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    final_context: str = ""
    response_continuation: str = ""
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
    active_child_id: str | None = None
    result: TaskResult | None = None
    reviewer_decisions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskStateStore:
    """Session-owned task tree with active-task traversal and transitions."""

    tasks: dict[str, Task] = field(default_factory=dict)
    root_task_id: str | None = None
    active_task_id: str | None = None
    transition_log: list[dict[str, Any]] = field(default_factory=list)

    _ALLOWED_TRANSITIONS: ClassVar[dict[TaskStatus, set[TaskStatus]]] = {
        TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
        TaskStatus.IN_PROGRESS: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.PENDING,
        },
        TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.FAILED},
        TaskStatus.FAILED: {TaskStatus.PENDING, TaskStatus.IN_PROGRESS},
        TaskStatus.COMPLETED: set(),
    }

    def create_task(
        self,
        title: str,
        *,
        parent_id: str | None = None,
        description: str = "",
    ) -> Task:
        """Create and store a task."""
        if parent_id is not None and parent_id not in self.tasks:
            msg = f"Parent task not found: {parent_id}"
            raise ValueError(msg)
        task = Task(title=title, parent_id=parent_id, description=description)
        self.tasks[task.task_id] = task
        if parent_id:
            self.tasks[parent_id].children.append(task.task_id)
        if self.root_task_id is None:
            self.root_task_id = task.task_id
        self._refresh_active_task()
        return task

    def decompose_task(self, task_id: str, subtasks: list[str]) -> list[str]:
        """Create child tasks only for an undecomposed parent.

        Decomposition is intentionally idempotent. Once a parent owns children,
        repeated analyzer/replan passes must refine metadata or focus on a local
        child, not append another copy of the same roadmap.
        """
        task = self.get_task(task_id)
        if task.children:
            return list(task.children)
        child_ids = []
        for title in subtasks:
            if title.strip():
                child_ids.append(self.create_task(title, parent_id=task_id).task_id)
        return child_ids

    def get_task(self, task_id: str) -> Task:
        """Return a task or raise a clear validation error."""
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            msg = f"Task not found: {task_id}"
            raise ValueError(msg) from exc

    def get_active_task(self) -> Task | None:
        """Return the active leaf task, refreshing traversal if needed."""
        if self.active_task_id not in self.tasks:
            self._refresh_active_task()
        if self.active_task_id is None:
            return None
        return self.tasks[self.active_task_id]

    def transition(self, task_id: str, status: TaskStatus | str) -> Task:
        """Transition a task after validating its lifecycle edge."""
        task = self.get_task(task_id)
        next_status = TaskStatus(status)
        allowed = self._ALLOWED_TRANSITIONS[task.status]
        if next_status != task.status and next_status not in allowed:
            msg = (
                "Invalid task transition "
                f"{task.status.value}->{next_status.value} for task {task_id}"
            )
            raise ValueError(msg)
        previous = task.status
        task.status = next_status
        self.transition_log.append(
            {
                "task_id": task_id,
                "from": previous.value,
                "to": next_status.value,
            }
        )
        self._refresh_active_task()
        return task

    def record_result(self, task_id: str, result: TaskResult) -> Task:
        """Persist task execution output without completing review state."""
        task = self.get_task(task_id)
        if task.status in {TaskStatus.PENDING, TaskStatus.FAILED}:
            self.transition(task_id, TaskStatus.IN_PROGRESS)
        task.result = result
        self._refresh_active_task()
        return task

    def record_reviewer_decision(
        self,
        task_id: str,
        decision: ReviewerDecision | str,
        *,
        rationale: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Append a reviewer decision to a task audit trail."""
        task = self.get_task(task_id)
        reviewer_decision = ReviewerDecision(decision)
        task.reviewer_decisions.append(
            {
                "decision": reviewer_decision.value,
                "rationale": rationale,
                "metadata": metadata or {},
            }
        )
        if reviewer_decision in {
            ReviewerDecision.NEEDS_REVISION,
            ReviewerDecision.REJECTED,
            ReviewerDecision.REPLAN,
        }:
            if task.status != TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.IN_PROGRESS
            self.active_task_id = task.task_id
        elif reviewer_decision == ReviewerDecision.APPROVED and task.result is not None:
            target = TaskStatus.COMPLETED if task.result.success else TaskStatus.FAILED
            if task.status != target:
                self.transition(task_id, target)
            self._complete_ready_parents()
            self._refresh_active_task()
        return task

    def add_artifact(
        self,
        task_id: str,
        *,
        path: str,
        kind: str = "file",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Attach an artifact reference to a task."""
        task = self.get_task(task_id)
        task.artifacts.append({"path": path, "kind": kind, "metadata": metadata or {}})
        return task

    def next_unfinished_leaf(self) -> Task | None:
        """Return the first leaf that still needs work.

        Failed tasks are intentionally unfinished in one-shot worker runs. A
        failed reviewed result means the same task must be retried or locally
        replanned/decomposed; it is not a terminal state that permits sibling
        advancement or final aggregation.
        """
        if self.root_task_id is None:
            return None

        def visit(task_id: str) -> Task | None:
            task = self.tasks[task_id]
            if task.children:
                for child_id in task.children:
                    found = visit(child_id)
                    if found is not None:
                        return found
                if task.status != TaskStatus.COMPLETED:
                    return task
                return None
            if task.status != TaskStatus.COMPLETED:
                return task
            return None

        return visit(self.root_task_id)

    def all_done(self) -> bool:
        """Return True only when every task is actually completed."""
        return bool(self.tasks) and all(
            task.status == TaskStatus.COMPLETED for task in self.tasks.values()
        )

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe task tree snapshot."""
        return {
            "root_task_id": self.root_task_id,
            "active_task_id": self.active_task_id,
            "tasks": {
                task_id: self._json_safe(asdict(task))
                for task_id, task in self.tasks.items()
            },
            "transition_log": list(self.transition_log),
        }

    def _refresh_active_task(self) -> None:
        """Refresh active_task_id to the first unfinished leaf."""
        active = self.next_unfinished_leaf()
        self.active_task_id = active.task_id if active is not None else None
        for task in self.tasks.values():
            task.active_child_id = None
        if active is None:
            return
        current = active
        while current.parent_id is not None and current.parent_id in self.tasks:
            parent = self.tasks[current.parent_id]
            parent.active_child_id = current.task_id
            current = parent

    def _complete_ready_parents(self) -> None:
        """Mark parent tasks complete when all descendants have finished."""
        changed = True
        while changed:
            changed = False
            for task in self.tasks.values():
                if not task.children or task.status == TaskStatus.COMPLETED:
                    continue
                children = [self.tasks[child_id] for child_id in task.children]
                if all(child.status == TaskStatus.COMPLETED for child in children):
                    if task.status == TaskStatus.PENDING:
                        task.status = TaskStatus.IN_PROGRESS
                    task.result = task.result or TaskResult(
                        content="Completed from child task results",
                        metadata={"aggregated": True},
                    )
                    task.status = TaskStatus.COMPLETED
                    changed = True

    def _json_safe(self, value: Any) -> Any:
        """Convert dataclass fields to JSON-compatible primitives."""
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, dict):
            return {key: self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
