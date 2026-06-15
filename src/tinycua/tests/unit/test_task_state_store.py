"""Task tree state contracts for the finalized runtime."""

from __future__ import annotations

import pytest

from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def test_task_store_tracks_active_task_and_traverses_unfinished_leaves() -> None:
    """Task store exposes an active leaf and advances after completion."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    assert store.active_task_id == first.task_id
    assert store.get_active_task() is first

    store.record_result(first.task_id, TaskResult(content="done"))

    assert store.active_task_id == second.task_id
    assert store.get_active_task() is second


def test_task_store_validates_status_transitions_and_records_reviewer_decisions() -> None:
    """Invalid lifecycle transitions fail instead of silently mutating state."""
    store = TaskStateStore()
    task = store.create_task("Write report")

    with pytest.raises(ValueError, match="Invalid task transition"):
        store.transition(task.task_id, TaskStatus.COMPLETED)

    store.transition(task.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="Missing evidence",
    )

    task_snapshot = store.snapshot()["tasks"][task.task_id]
    assert task.status == TaskStatus.IN_PROGRESS
    assert task_snapshot["reviewer_decisions"][-1]["decision"] == "needs_revision"
    assert task_snapshot["reviewer_decisions"][-1]["rationale"] == "Missing evidence"
