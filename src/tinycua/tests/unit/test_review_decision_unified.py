"""Unit tests for unified needs_revision/rejected routing (Milestone 8, FR-057)."""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus
from tinycua.tools.task_tools import TaskReviewDecisionTool


def _record_send_back(
    store: TaskStateStore, task_id: str, decision: ReviewerDecision
) -> None:
    """Record a send-back against one stable actionable finding."""
    open_findings = [
        finding
        for finding in store.get_task(task_id).review_findings
        if finding.get("status") == "OPEN"
    ]
    metadata = (
        {
            "finding_updates": [
                {"finding_id": open_findings[-1]["finding_id"], "status": "OPEN"}
            ]
        }
        if open_findings
        else {"new_findings": ["The task needs revision."]}
    )
    store.record_reviewer_decision(task_id, decision, metadata=metadata)


class TestNeedsRevisionRejectedUnified:
    """FR-057: needs_revision and rejected are aliases — same routing + counting."""

    def test_both_increment_consecutive_failures_identically(self):
        # needs_revision
        store1 = TaskStateStore()
        root1 = store1.create_task("Root")
        child1 = store1.create_task("Child", parent_id=root1.task_id)
        store1.transition(child1.task_id, TaskStatus.IN_PROGRESS)
        for _ in range(3):
            _record_send_back(store1, child1.task_id, ReviewerDecision.NEEDS_REVISION)
        assert child1.consecutive_failures == 3

        # rejected
        store2 = TaskStateStore()
        root2 = store2.create_task("Root")
        child2 = store2.create_task("Child", parent_id=root2.task_id)
        store2.transition(child2.task_id, TaskStatus.IN_PROGRESS)
        for _ in range(3):
            _record_send_back(store2, child2.task_id, ReviewerDecision.REJECTED)
        assert child2.consecutive_failures == 3

    def test_both_route_through_same_schedule_after_review_branch(self):
        """Both needs_revision and rejected trigger the same threshold-gated replan."""
        for decision in (ReviewerDecision.NEEDS_REVISION, ReviewerDecision.REJECTED):
            store = TaskStateStore()
            root = store.create_task("Root")
            child = store.create_task("Child", parent_id=root.task_id)
            store.transition(child.task_id, TaskStatus.IN_PROGRESS)
            store.record_result(child.task_id, TaskResult(content="attempt"))
            for _ in range(5):
                _record_send_back(store, child.task_id, decision)
            queue = NodeQueue()

            WorkerRuntimeController(store, max_replans=3).schedule_after_review(
                queue, reviewed_task_id=child.task_id, decision=decision
            )

            # Both should route to replan (assessor + analyzer).
            ids = [n.node_id for n in queue.items]
            assert "task_analyzer" in ids

    def test_both_set_task_to_in_progress(self):
        for decision in (ReviewerDecision.NEEDS_REVISION, ReviewerDecision.REJECTED):
            store = TaskStateStore()
            root = store.create_task("Root")
            child = store.create_task("Child", parent_id=root.task_id)
            store.transition(child.task_id, TaskStatus.IN_PROGRESS)
            _record_send_back(store, child.task_id, decision)
            assert child.status == TaskStatus.IN_PROGRESS
            assert store.active_task_id == child.task_id


class TestTaskReviewDecisionToolDescription:
    """Legacy rejected state remains parseable but is not model-facing."""

    def test_description_retires_rejected(self):
        tool = TaskReviewDecisionTool()
        description = tool.description.lower()
        assert "needs_revision" in description
        assert "rejected" not in description
        assert ReviewerDecision("rejected") is ReviewerDecision.REJECTED
