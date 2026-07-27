"""Assessed cancellation contracts."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import (
    TinyCUAResultAggregationNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.session import Session
from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus
from tinycua.tools.handoff_tools import TaskAssessmentDecisionTool
from tinycua.tools.task_tools import TaskShrinkTool


def test_cancellation_request_keeps_task_runnable_until_approved() -> None:
    """A cancellation request is not terminal before TaskAssessor approves it."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Obsolete research", parent_id=root.task_id)

    request = store.request_task_cancellation(task.task_id, "Not needed for scope.")

    assert request["state"] == "pending"
    assert task.status == TaskStatus.PENDING
    assert store.active_task_id == task.task_id


def test_cancellation_approval_cascades_only_unattempted_descendants() -> None:
    """Approved parent cancellation retires the unfinished local subtree atomically."""
    store = TaskStateStore()
    root = store.create_task("Root")
    parent = store.create_task("Obsolete branch", parent_id=root.task_id)
    leaf = store.create_task("Unneeded leaf", parent_id=parent.task_id)
    completed = store.create_task("Completed evidence", parent_id=parent.task_id)
    store.record_result(completed.task_id, TaskResult(content="done", success=True))
    store.transition(completed.task_id, TaskStatus.COMPLETED)
    request = store.request_task_cancellation(
        parent.task_id, "Covered by another path."
    )

    store.assess_task_cancellation(
        request["request_id"], approved=True, rationale="No user requirement is lost."
    )

    assert parent.status == TaskStatus.CANCELLED
    assert leaf.status == TaskStatus.CANCELLED
    assert completed.status == TaskStatus.COMPLETED
    assert parent.metadata["cancellation_request"]["state"] == "approved"
    assert leaf.metadata["cancellation_request"]["request_id"] == request["request_id"]


def test_cancellation_rejection_preserves_task_and_allows_later_request() -> None:
    """A rejected request is auditable but does not permanently block future evidence."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Potentially obsolete", parent_id=root.task_id)
    first = store.request_task_cancellation(task.task_id, "Seems unnecessary.")

    store.assess_task_cancellation(
        first["request_id"], approved=False, rationale="Still required by the request."
    )
    second = store.request_task_cancellation(
        task.task_id, "Now covered by replacement."
    )

    assert task.status == TaskStatus.PENDING
    assert first["request_id"] != second["request_id"]
    assert second["state"] == "pending"


def test_cancellation_request_rejects_attempted_work_and_duplicate_pending_request() -> (
    None
):
    """Cancellation cannot dispose of attempted work or create duplicate reviews."""
    store = TaskStateStore()
    root = store.create_task("Root")
    pending = store.create_task("Pending", parent_id=root.task_id)
    attempted = store.create_task("Attempted", parent_id=root.task_id)
    store.record_result(attempted.task_id, TaskResult(content="failed", success=False))

    request = store.request_task_cancellation(pending.task_id, "Out of scope.")

    with pytest.raises(ValueError, match="pending cancellation"):
        store.request_task_cancellation(pending.task_id, "Still out of scope.")
    store.assess_task_cancellation(
        request["request_id"], approved=False, rationale="Still needed."
    )
    with pytest.raises(ValueError, match="attempted work"):
        store.request_task_cancellation(attempted.task_id, "Out of scope.")


def test_cancellation_assessment_is_exactly_once_per_request() -> None:
    """Only the pending request can receive one committed Assessor decision."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Obsolete", parent_id=root.task_id)
    request = store.request_task_cancellation(task.task_id, "No longer needed.")

    store.assess_task_cancellation(
        request["request_id"], approved=False, rationale="Still required."
    )

    with pytest.raises(ValueError, match="pending"):
        store.assess_task_cancellation(
            request["request_id"], approved=True, rationale="Changed mind."
        )


def test_cancellation_approval_rejects_work_attempted_after_request() -> None:
    """State validation prevents an escaped Executor from being retired afterward."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Obsolete", parent_id=root.task_id)
    request = store.request_task_cancellation(task.task_id, "Covered.")
    store.transition(task.task_id, TaskStatus.IN_PROGRESS)

    with pytest.raises(ValueError, match="attempted work"):
        store.assess_task_cancellation(
            request["request_id"], approved=True, rationale="Coverage holds."
        )

    assert task.status == TaskStatus.IN_PROGRESS
    assert task.metadata["cancellation_request"]["state"] == "pending"


def test_task_shrink_requests_and_assessor_tool_approves_cancellation() -> None:
    """Existing tool entrypoint requires the bound Assessor's approval."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Obsolete", parent_id=root.task_id)
    shrink = TaskShrinkTool()
    shrink.bind_task_store(store)

    requested = shrink("cancel", task.task_id, "Covered by another task.")
    assessor = TaskAssessmentDecisionTool()
    assessor.bind_task_store(store)
    assessor.bind_handoff_store([])
    assessor.bind_source_node("task_assessor")
    assessor.bind_assessment_mode("cancellation_review")
    assessor.bind_cancellation_request_id(requested["cancellation_request_id"])
    approved = assessor(
        "ready", findings=[], advisories=[], rationale="Coverage holds."
    )

    assert requested["cancellation_state"] == "pending"
    assert approved["success"] is True
    assert task.status == TaskStatus.CANCELLED


def test_cancellation_assessor_rejection_returns_blocking_finding() -> None:
    """A rejected cancellation sends its target back for Analyzer repair."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Required", parent_id=root.task_id)
    request = store.request_task_cancellation(task.task_id, "Seems difficult.")
    assessor = TaskAssessmentDecisionTool()
    handoffs = []
    assessor.bind_task_store(store)
    assessor.bind_handoff_store(handoffs)
    assessor.bind_source_node("task_assessor")
    assessor.bind_assessment_mode("cancellation_review")
    assessor.bind_cancellation_request_id(request["request_id"])

    rejected = assessor(
        "analyze",
        findings=[{"task_id": task.task_id, "finding": "The user still requires it."}],
        advisories=[],
        rationale="Difficulty is not a cancellation reason.",
    )

    assert rejected["success"] is True
    assert rejected["selected_task_ids"] == [task.task_id]
    assert task.status == TaskStatus.PENDING
    assert task.metadata["cancellation_request"]["state"] == "rejected"
    assert handoffs[0].target_node == "task_analyzer"


def test_analyzer_inserts_cancellation_assessor_before_execution() -> None:
    """A newly requested cancellation cannot advance directly to Executor."""
    session = Session()
    root = session.task_store.create_task("Root")
    task = session.task_store.create_task("Obsolete", parent_id=root.task_id)
    request = session.task_store.request_task_cancellation(task.task_id, "Covered.")
    analyzer = TinyCUATaskAnalyzerNode(
        "task_analyzer", create_node_config("task_analyzer")
    )
    executor = TinyCUATaskExecutorNode(
        "task_executor", create_node_config("task_executor")
    )
    analyzer.ensure_session(session)
    queue = NodeQueue(items=[analyzer, executor])

    analyzer.on_complete(queue, LLMResult(content="requested"))

    assert [node.node_id for node in queue.items] == [
        "task_analyzer",
        "task_assessor",
        "task_analyzer",
        "task_executor",
    ]
    assert queue.items[1].config.metadata["task_assessor_mode"] == "cancellation_review"
    assert (
        queue.items[1].config.metadata["cancellation_request_id"]
        == request["request_id"]
    )


def test_aggregation_discloses_approved_cancellation() -> None:
    """Cancellation remains visible rather than silently disappearing from output."""
    session = Session()
    root = session.task_store.create_task("Root")
    task = session.task_store.create_task("Obsolete", parent_id=root.task_id)
    request = session.task_store.request_task_cancellation(task.task_id, "Covered.")
    session.task_store.assess_task_cancellation(
        request["request_id"], approved=True, rationale="Coverage holds."
    )
    node = TinyCUAResultAggregationNode(
        "result_aggregation", create_node_config("result_aggregation")
    )
    node.ensure_session(session)

    aggregated = node._build_aggregated_result("Done.")

    assert aggregated.task_summaries == ["[CANCELLED] Obsolete: Covered."]
