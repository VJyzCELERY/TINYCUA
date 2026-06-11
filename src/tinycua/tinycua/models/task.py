"""Task, TaskResult, and ReviewerDecision data models for Milestone 3.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TaskStatus = Literal["pending", "in_progress", "blocked", "done", "failed"]
ExecutionStatus = Literal["not_started", "running", "succeeded", "failed", "blocked", "max_iterations_reached"]
ReviewerOutcome = Literal["accept", "retry", "replan", "open_question"]


@dataclass
class Task:
    """Tree node representing a unit of work in the task tree.

    Attributes:
        task_id: Unique identifier for this task.
        title: Human-readable title.
        description: Optional longer description.
        status: Current lifecycle status.
        children: Append-only list of child tasks.
        active_child_id: Hint for DFS traversal — which child to resume from.
        result: Execution result, if available.
        metadata: Arbitrary key-value metadata.
    """

    task_id: str
    title: str
    description: str = ""
    status: TaskStatus = "pending"
    children: list[Task] = field(default_factory=list)
    active_child_id: str | None = None
    result: TaskResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Execution outcome for a task.

    Attributes:
        task_id: The task this result belongs to.
        execution_status: Current execution status.
        reviewer_decision: Review decision, if available.
        summary: Human-readable summary of execution.
        artifacts: List of artifact dicts produced by execution.
        metadata: Arbitrary key-value metadata.
    """

    task_id: str
    execution_status: ExecutionStatus = "not_started"
    reviewer_decision: ReviewerDecision | None = None
    summary: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewerDecision:
    """Review outcome for a task result.

    Attributes:
        outcome: Reviewer's decision.
        rationale: Optional explanation for the decision.
        target_task_id: Optional target task for the decision (e.g., for replan).
        metadata: Arbitrary key-value metadata.
    """

    outcome: ReviewerOutcome
    rationale: str | None = None
    target_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
