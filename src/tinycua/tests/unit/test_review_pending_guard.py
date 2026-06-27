"""FR-5: prevent completing/updating out-of-order tasks.

FR-5a: ``record_reviewer_decision`` rejects ``approved`` on a PENDING leaf
with no result and no children (a task that was never dispatched). The
FR-079 fallback (auto-generate result for IN_PROGRESS tasks whose executor
forgot ``task_result_update``) remains unchanged.

FR-5b: ``record_result`` does not auto-transition a non-active task from
PENDING/FAILED to IN_PROGRESS. Only the active task auto-transitions; a
non-active task keeps its status even when a result is recorded on it
(the executor sibling-propagation path). The task must become active
first.
"""

from __future__ import annotations

import pytest

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import (
    ReviewerDecision,
    TaskResult,
    TaskStateStore,
    TaskStatus,
)
from tinycua.tools.task_tools import TaskReviewDecisionTool


class TestApprovePendingTaskGuard:
    """FR-5a: approving a never-dispatched task is rejected."""

    def test_approve_pending_leaf_rejected(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        with pytest.raises(ValueError, match="never executed"):
            store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        # Task stays PENDING — no fake result, no status change.
        assert child.status == TaskStatus.PENDING
        assert child.result is None

    def test_approve_in_progress_no_result_still_works(self):
        """FR-079 case: IN_PROGRESS, no result → fallback fires (unchanged)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        assert child.result is not None
        assert child.result.metadata.get("auto_generated") is True
        assert child.status == TaskStatus.COMPLETED

    def test_approve_parent_all_children_done_still_works(self):
        """Parent PENDING, all children COMPLETED → aggregated result (unchanged)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        assert root.result is not None
        assert root.result.metadata.get("aggregated") is True
        assert root.status == TaskStatus.COMPLETED

    def test_tool_catches_error_and_returns_failure(self):
        """TaskReviewDecisionTool catches ValueError → success=False."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        tool = TaskReviewDecisionTool()
        tool.bind_task_store(store)
        result = tool(task_id=child.task_id, decision="approved", rationale="x")
        assert result["success"] is False
        assert "never executed" in result["error"]
        # Task stays PENDING.
        assert child.status == TaskStatus.PENDING
        assert child.result is None


class TestRecordResultNonActiveGuard:
    """FR-5b: record_result on a non-active task keeps it PENDING/FAILED."""

    def test_record_result_on_non_active_keeps_pending(self):
        """Two tasks; record_result on second (non-active) → stays PENDING, has result."""
        store = TaskStateStore()
        root = store.create_task("Root")
        first = store.create_task("First", parent_id=root.task_id)
        second = store.create_task("Second", parent_id=root.task_id)
        # first is the active task (post-order leaf).
        assert store.active_task_id == first.task_id
        # record_result on second (non-active) — stays PENDING.
        store.record_result(second.task_id, TaskResult(content="sibling work", success=True))
        assert second.result is not None
        assert second.status == TaskStatus.PENDING  # not auto-transitioned

    def test_record_result_on_active_auto_transitions(self):
        """Active task; record_result → IN_PROGRESS (unchanged)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        assert store.active_task_id == child.task_id
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        assert child.status == TaskStatus.IN_PROGRESS

    def test_executor_sibling_propagation_still_works(self):
        """record_result on sibling (non-active) → PENDING + result; after active
        approved, sibling becomes active; schedule_next returns
        ["result_reviewer"] (skip executor)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        first = store.create_task("First", parent_id=root.task_id)
        second = store.create_task("Second", parent_id=root.task_id)
        # Executor completes first AND reports result for second.
        store.record_result(first.task_id, TaskResult(content="did both", success=True))
        store.record_result(
            second.task_id,
            TaskResult(content="completed as part of task 1", success=True),
        )
        # second stays PENDING (non-active) but has a result.
        assert second.status == TaskStatus.PENDING
        assert second.result is not None
        # Reviewer approves first → active moves to second.
        store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
        # Now second is active and has a result → schedule_next skips executor.
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["result_reviewer"]  # no executor — work already done