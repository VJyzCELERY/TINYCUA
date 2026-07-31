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
    store.record_reviewer_decision(
        active.task_id,
        ReviewerDecision.NEEDS_REVISION,
        metadata={"new_findings": ["The task needs revision."]},
    )
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(
        queue, reviewed_task_id=active.task_id, decision="needs_revision"
    )

    assert store.active_task_id == active.task_id
    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]


def test_worker_runtime_repeated_revision_never_routes_to_response() -> None:
    """Incomplete tasks keep executing/reviewing until reviewer-owned completion."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    # Use 3 rejections — below the default replan_threshold of 5, so this
    # still routes to executor+reviewer (retry), not replan.
    store.record_reviewer_decision(
        active.task_id,
        ReviewerDecision.NEEDS_REVISION,
        metadata={"new_findings": ["The task needs revision."]},
    )
    for _ in range(2):
        store.record_reviewer_decision(
            active.task_id,
            ReviewerDecision.NEEDS_REVISION,
            metadata={
                "finding_updates": [{"finding_id": "finding-1", "status": "OPEN"}]
            },
        )
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(
        queue, reviewed_task_id=active.task_id, decision="needs_revision"
    )

    assert store.all_done() is False
    assert store.active_task_id == active.task_id
    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]


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
    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]

    store.record_result(second.task_id, TaskResult(content="ok"))
    store.record_reviewer_decision(second.task_id, ReviewerDecision.APPROVED)
    queue = NodeQueue()
    WorkerRuntimeController(store).schedule_next(queue)
    # Parent tasks now get a verification pass (executor verifies, reviewer
    # approves) — not auto-completed. So the root is scheduled for execution.
    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]

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
    store.transition(first.task_id, TaskStatus.FAILED)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(
        queue, reviewed_task_id=first.task_id, decision="needs_revision"
    )

    assert first.status == TaskStatus.FAILED
    assert second.status == TaskStatus.PENDING
    assert store.active_task_id == first.task_id
    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]


def test_worker_runtime_skips_cancelled_active_leaf() -> None:
    """A disposed leaf is never retried; its sibling becomes executable."""
    store = TaskStateStore()
    root = store.create_task("Root")
    impossible = store.create_task("Impossible", parent_id=root.task_id)
    remaining = store.create_task("Remaining", parent_id=root.task_id)
    request = store.request_task_cancellation(
        impossible.task_id, "source lacks benchmark data"
    )
    store.assess_task_cancellation(
        request["request_id"], approved=True, rationale="The task is unnecessary."
    )
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_next(queue)

    assert store.active_task_id == remaining.task_id
    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]


def test_worker_runtime_replan_uses_local_assessor_mode() -> None:
    """Reviewer replan scopes TaskAssessor to active/local task region."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.REPLAN)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(
        queue, reviewed_task_id=active.task_id, decision="replan"
    )

    assert [node.node_id for node in queue.items] == [
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
    ]
    assert queue.items[0].config.metadata["task_assessor_mode"] == "local_replan"
    assert queue.items[1].config.metadata["task_analyzer_mode"] == "local_replan"
    assert queue.items[0].config.metadata["replan_task_id"] == active.task_id
    assert queue.items[1].config.metadata["replan_task_id"] == active.task_id


def test_open_question_replans_instead_of_bailing_to_response() -> None:
    """OPEN_QUESTION keeps incomplete work inside the worker loop."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.OPEN_QUESTION)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(
        queue, reviewed_task_id=active.task_id, decision="open_question"
    )

    assert [node.node_id for node in queue.items] == [
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
    ]


def test_open_question_enabled_replans_instead_of_bailing_to_response() -> None:
    """OPEN_QUESTION never bypasses incomplete work."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(active.task_id, ReviewerDecision.OPEN_QUESTION)
    queue = NodeQueue()

    WorkerRuntimeController(
        store, enable_open_question_review=True
    ).schedule_after_review(
        queue, reviewed_task_id=active.task_id, decision="open_question"
    )

    assert [node.node_id for node in queue.items] == [
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
    ]


def test_worker_runtime_uses_explicit_reviewed_task_after_postponement() -> None:
    """Scheduling uses the committed verdict, not the newly selected sibling."""
    store = TaskStateStore()
    root = store.create_task("Root")
    reviewed = store.create_task("Blocked", parent_id=root.task_id)
    sibling = store.create_task("Runnable", parent_id=root.task_id)
    store.record_result(reviewed.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(
        reviewed.task_id, "postpone_siblings", rationale="run sibling first"
    )
    assert store.active_task_id == sibling.task_id
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(
        queue,
        reviewed_task_id=reviewed.task_id,
        decision="postpone_siblings",
    )

    assert [node.node_id for node in queue.items] == [
        "task_executor",
        "result_reviewer",
    ]
    assert store.active_task_id == sibling.task_id
