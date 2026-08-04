"""Unit tests for auto-replan on consecutive reviewer rejections (Milestone 6, Stream A)."""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def _record_rejection(
    store: TaskStateStore, task_id: str, rationale: str = "Persistent defect."
) -> None:
    """Record one rejection while preserving a stable actionable finding."""
    task = store.get_task(task_id)
    open_findings = [
        finding for finding in task.review_findings if finding.get("status") == "OPEN"
    ]
    metadata = (
        {
            "finding_updates": [
                {"finding_id": open_findings[-1]["finding_id"], "status": "OPEN"}
            ]
        }
        if open_findings
        else {"new_findings": [rationale]}
    )
    store.record_reviewer_decision(
        task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale=rationale,
        metadata=metadata,
    )


def _resolve_open_findings(store: TaskStateStore, task_id: str) -> dict:
    """Return updates that resolve every current finding before approval."""
    return {
        "finding_updates": [
            {"finding_id": finding["finding_id"], "status": "ADDRESSED"}
            for finding in store.get_task(task_id).review_findings
            if finding.get("status") == "OPEN"
        ]
    }


class TestConsecutiveFailures:
    """Task.consecutive_failures counts backward until an approval."""

    def test_all_rejections(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        for _ in range(3):
            _record_rejection(store, child.task_id)
        assert child.consecutive_failures == 3

    def test_approve_resets_count(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        # Approval terminates the task and breaks the rejection run.
        for _ in range(3):
            _record_rejection(store, child.task_id)
        store.record_result(child.task_id, TaskResult(content="ok"))
        store.record_reviewer_decision(
            child.task_id,
            ReviewerDecision.APPROVED,
            metadata=_resolve_open_findings(store, child.task_id),
        )
        assert child.consecutive_failures == 0

    def test_no_decisions(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        assert root.consecutive_failures == 0

    def test_replan_counts_as_failure(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_reviewer_decision(child.task_id, ReviewerDecision.REPLAN)
        _record_rejection(store, child.task_id)
        assert child.consecutive_failures == 2


class TestAutoReplanThreshold:
    """schedule_after_review triggers replan after threshold consecutive rejections."""

    def test_5_consecutive_rejections_trigger_replan(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        for _ in range(5):
            _record_rejection(store, child.task_id)
        queue = NodeQueue()

        WorkerRuntimeController(store).schedule_after_review(
            queue, reviewed_task_id=child.task_id, decision="needs_revision"
        )

        # Should route to assessor+analyzer (replan), not executor+reviewer
        ids = [n.node_id for n in queue.items]
        assert "task_assessor" in ids
        assert "task_analyzer" in ids
        assert "task_executor" not in ids or ids.index("task_assessor") < ids.index(
            "task_executor"
        )

    def test_4_consecutive_rejections_still_retry(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        for _ in range(4):
            _record_rejection(store, child.task_id)
        queue = NodeQueue()

        WorkerRuntimeController(store).schedule_after_review(
            queue, reviewed_task_id=child.task_id, decision="needs_revision"
        )

        # Should route to executor+reviewer (retry), not replan
        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_approve_resets_consecutive_count(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt1"))
        # 4 rejections, then approve, then 4 more rejections
        for _ in range(4):
            _record_rejection(store, child.task_id)
        store.record_reviewer_decision(
            child.task_id,
            ReviewerDecision.APPROVED,
            metadata=_resolve_open_findings(store, child.task_id),
        )
        # After approve, the task is completed. Re-create the scenario.
        child2 = store.create_task("Child2", parent_id=root.task_id)
        store.transition(child2.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child2.task_id, TaskResult(content="attempt2"))
        for _ in range(4):
            _record_rejection(store, child2.task_id)
        queue = NodeQueue()

        WorkerRuntimeController(store).schedule_after_review(
            queue, reviewed_task_id=child2.task_id, decision="needs_revision"
        )

        # 4 < 5 → still retry
        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_replan_threshold_configurable(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        for _ in range(5):
            _record_rejection(store, child.task_id)
        queue = NodeQueue()

        # threshold=7 → 5 < 7 → still retry
        WorkerRuntimeController(store, replan_threshold=7).schedule_after_review(
            queue, reviewed_task_id=child.task_id, decision="needs_revision"
        )

        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_replan_includes_rationale_in_reason(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        for _ in range(3):
            _record_rejection(store, child.task_id)
        _record_rejection(store, child.task_id, "auth missing JWT")
        _record_rejection(store, child.task_id, "integration test fails")
        queue = NodeQueue()

        ctrl = WorkerRuntimeController(store)
        ctrl.schedule_after_review(
            queue, reviewed_task_id=child.task_id, decision="needs_revision"
        )

        # The analyzer config should have a replan_reason with the rationales.
        analyzer = next(n for n in queue.items if n.node_id == "task_analyzer")
        reason = analyzer.config.metadata.get("replan_reason", "")
        assert "auth missing JWT" in reason or "integration test fails" in reason
