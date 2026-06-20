"""State-driven worker runtime controller contracts."""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def test_worker_runtime_retry_keeps_same_active_task() -> None:
    """Reviewer retry routes back to task_executor without advancing active task."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.NEEDS_REVISION)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    assert store.active_task_id == active.task_id
    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]


def test_worker_runtime_repeated_revision_never_routes_to_response() -> None:
    """Incomplete tasks keep executing/reviewing until reviewer-owned completion."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    for _ in range(5):
        store.record_reviewer_decision(active.task_id, ReviewerDecision.NEEDS_REVISION)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    assert store.all_done() is False
    assert store.active_task_id == active.task_id
    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]


def test_worker_runtime_completed_task_advances_until_aggregation_ready() -> None:
    """Accepted leaf completion advances to next leaf, then aggregation."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="ok"))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_next(queue)
    assert store.active_task_id == second.task_id
    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]

    store.record_result(second.task_id, TaskResult(content="ok"))
    store.record_reviewer_decision(second.task_id, ReviewerDecision.APPROVED)
    queue = NodeQueue()
    WorkerRuntimeController(store).schedule_next(queue)
    # Parent tasks now get a verification pass (executor verifies, reviewer
    # approves) — not auto-completed. So the root is scheduled for execution.
    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]

    # Complete the root verification pass → aggregation fires.
    store.record_result(root.task_id, TaskResult(content="root verified"))
    store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
    queue = NodeQueue()
    WorkerRuntimeController(store).schedule_next(queue)
    assert [node.node_id for node in queue.items] == ["result_aggregation"]


def test_worker_runtime_failed_task_retries_same_leaf() -> None:
    """A failed leaf does not advance to siblings or aggregation."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="failed", success=False))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    assert first.status == TaskStatus.FAILED
    assert second.status == TaskStatus.PENDING
    assert store.active_task_id == first.task_id
    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]


def test_worker_runtime_replan_uses_local_assessor_mode() -> None:
    """Reviewer replan scopes TaskAssessor to active/local task region."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.REPLAN)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    assert [node.node_id for node in queue.items] == [
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
    ]
    assert queue.items[0].config.metadata["task_assessor_mode"] == "local_replan"
    assert queue.items[1].config.metadata["task_analyzer_mode"] == "local_replan"
