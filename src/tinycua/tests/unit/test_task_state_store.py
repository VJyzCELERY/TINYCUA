"""Task tree state contracts for the finalized runtime."""

from __future__ import annotations

import pytest

from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def test_task_store_advances_after_reviewer_approval() -> None:
    """Executor result alone does not advance; reviewer approval does."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    assert store.active_task_id == first.task_id
    assert store.get_active_task() is first

    store.record_result(first.task_id, TaskResult(content="done"))
    assert first.status == TaskStatus.IN_PROGRESS
    assert store.active_task_id == first.task_id

    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)

    assert store.active_task_id == second.task_id
    assert store.get_active_task() is second


def test_approved_result_does_not_auto_share_context() -> None:
    """Reviewer approval does not automatically copy context to unfinished tasks."""
    store = TaskStateStore()
    root = store.create_task("Build app")
    scaffold = store.create_task("Create project scaffold", parent_id=root.task_id)
    module = store.create_task("Create module x", parent_id=root.task_id)

    store.record_result(
        scaffold.task_id,
        TaskResult(content="Created backend/app.py and frontend/index.html."),
    )
    store.record_reviewer_decision(scaffold.task_id, ReviewerDecision.APPROVED)

    assert scaffold.status == TaskStatus.COMPLETED
    # Context is NOT automatically shared — the reviewer curates it manually
    assert "context" not in module.metadata


def test_failed_leaf_remains_active_and_not_done() -> None:
    """Failed reviewed leaves are retry targets, not completed work."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    store.record_result(first.task_id, TaskResult(content="failed", success=False))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)

    assert first.status == TaskStatus.FAILED
    assert second.status == TaskStatus.PENDING
    assert store.active_task_id == first.task_id
    assert store.get_active_task() is first
    assert store.all_done() is False


def test_failed_leaf_can_be_retried_and_completed() -> None:
    """A failed leaf reopens when new executor evidence is recorded."""
    store = TaskStateStore()
    task = store.create_task("Retry me")

    store.record_result(task.task_id, TaskResult(content="failed", success=False))
    store.record_reviewer_decision(task.task_id, ReviewerDecision.APPROVED)
    assert task.status == TaskStatus.FAILED

    store.record_result(task.task_id, TaskResult(content="fixed", success=True))
    store.record_reviewer_decision(task.task_id, ReviewerDecision.APPROVED)

    assert task.status == TaskStatus.COMPLETED
    assert store.active_task_id is None
    assert store.all_done() is True


def test_decompose_existing_parent_is_idempotent() -> None:
    """Repeated decomposition should not append duplicate child trees."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)

    child_ids = store.decompose_task(root.task_id, ["First", "Second"])

    assert child_ids == [first.task_id]
    assert store.tasks[root.task_id].children == [first.task_id]


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
