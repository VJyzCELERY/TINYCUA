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


def test_worker_runtime_completed_task_advances_until_aggregation_ready() -> None:
    """Accepted leaf completion advances to next leaf, then aggregation."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="ok"))
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_next(queue)
    assert store.active_task_id == second.task_id
    assert [node.node_id for node in queue.items] == ["task_assessor", "task_executor", "result_reviewer"]

    store.record_result(second.task_id, TaskResult(content="ok"))
    queue = NodeQueue()
    WorkerRuntimeController(store).schedule_next(queue)
    assert [node.node_id for node in queue.items] == ["result_aggregation"]


def test_worker_runtime_open_question_routes_to_terminal_response() -> None:
    """Reviewer open questions must not proceed with execution or aggregation."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Needs clarification", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.OPEN_QUESTION)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    assert [node.node_id for node in queue.items] == ["response"]
