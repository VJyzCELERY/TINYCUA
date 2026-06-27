"""State-driven worker runtime controller contracts."""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def test_replan_threshold_default_is_three() -> None:
    """FR-1: default replan_threshold is 3, not 5."""
    store = TaskStateStore()
    ctrl = WorkerRuntimeController(store)
    assert ctrl.replan_threshold == 3


def test_replan_threshold_explicit_override_wins() -> None:
    """FR-1: explicit replan_threshold still wins over default."""
    store = TaskStateStore()
    ctrl = WorkerRuntimeController(store, replan_threshold=7)
    assert ctrl.replan_threshold == 7


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
    # Use 2 rejections — below the default replan_threshold of 3, so this
    # still routes to executor+reviewer (retry), not replan.
    for _ in range(2):
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


def test_open_question_disabled_by_default_falls_through_to_schedule_next() -> None:
    """OPEN_QUESTION decision with flag disabled (default) does not bail to ResponseNode.

    The controller must treat OPEN_QUESTION as an unknown decision and fall
    through to schedule_next — it must never route to ResponseNode while
    tasks remain unfinished in one-shot worker mode.
    """
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.OPEN_QUESTION)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    # Falls through to schedule_next → executor+reviewer (active task unfinished)
    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]


def test_open_question_enabled_routes_to_response_node() -> None:
    """OPEN_QUESTION decision with flag enabled bails to ResponseNode."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.OPEN_QUESTION)
    queue = NodeQueue()

    WorkerRuntimeController(
        store, enable_open_question_review=True
    ).schedule_after_review(queue)

    assert [node.node_id for node in queue.items] == ["response"]
