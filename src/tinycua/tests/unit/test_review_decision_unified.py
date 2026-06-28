"""Unit tests for unified needs_revision/rejected routing (Milestone 8, FR-057)."""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus
from tinycua.tools.task_tools import TaskReviewDecisionTool


class TestNeedsRevisionRejectedUnified:
    """FR-057: needs_revision and rejected are aliases — same routing + counting."""

    def test_both_increment_consecutive_failures_identically(self):
        # needs_revision
        store1 = TaskStateStore()
        root1 = store1.create_task("Root")
        child1 = store1.create_task("Child", parent_id=root1.task_id)
        store1.transition(child1.task_id, TaskStatus.IN_PROGRESS)
        for _ in range(3):
            store1.record_reviewer_decision(child1.task_id, ReviewerDecision.NEEDS_REVISION)
        assert child1.consecutive_failures == 3

        # rejected
        store2 = TaskStateStore()
        root2 = store2.create_task("Root")
        child2 = store2.create_task("Child", parent_id=root2.task_id)
        store2.transition(child2.task_id, TaskStatus.IN_PROGRESS)
        for _ in range(3):
            store2.record_reviewer_decision(child2.task_id, ReviewerDecision.REJECTED)
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
                store.record_reviewer_decision(child.task_id, decision)
            queue = NodeQueue()

            WorkerRuntimeController(store, max_replans=3).schedule_after_review(queue)

            # Both should route to replan (assessor + analyzer).
            ids = [n.node_id for n in queue.items]
            assert "task_analyzer" in ids

    def test_both_set_task_to_in_progress(self):
        for decision in (ReviewerDecision.NEEDS_REVISION, ReviewerDecision.REJECTED):
            store = TaskStateStore()
            root = store.create_task("Root")
            child = store.create_task("Child", parent_id=root.task_id)
            store.transition(child.task_id, TaskStatus.IN_PROGRESS)
            store.record_reviewer_decision(child.task_id, decision)
            assert child.status == TaskStatus.IN_PROGRESS
            assert store.active_task_id == child.task_id


class TestTaskReviewDecisionToolDescription:
    """FR-057: the tool description documents rejected as an alias for needs_revision."""

    def test_description_documents_aliasing(self):
        tool = TaskReviewDecisionTool()
        description = tool.description.lower()
        assert "alias" in description or "equivalent" in description
        assert "needs_revision" in description
        assert "rejected" in description