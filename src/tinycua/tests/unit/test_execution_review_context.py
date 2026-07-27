"""Task-local execution review journal and context isolation contracts."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.session import Session
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore
from tinycua.tools.task_tools import TaskInspectTool, TaskReviewDecisionTool


def _review_tool(store: TaskStateStore) -> TaskReviewDecisionTool:
    tool = TaskReviewDecisionTool()
    tool.bind_task_store(store)
    tool.bind_source_node("result_reviewer")
    return tool


def test_approval_does_not_copy_result_or_metadata_to_sibling() -> None:
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="private sibling result"))

    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)

    assert second.metadata == {}


def test_review_commit_is_atomic_and_approval_requires_open_findings_resolved() -> None:
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    future = store.create_task("Future", parent_id=root.task_id)
    store.record_result(active.task_id, TaskResult(content="attempt"))
    review = _review_tool(store)

    staged = review(
        decision="needs_revision",
        review_summary="Missing verification",
        rationale="The output exists, but no command verified it.",
        new_findings=["Run the focused verification command."],
        finding_updates=[],
    )
    assert staged["success"]
    store.commit_staged_reviewer_decision(active.task_id)

    event = active.reviewer_decisions[-1]
    assert event["event_id"] == "review-1"
    assert event["review_summary"] == "Missing verification"
    assert active.review_findings == [
        {
            "finding_id": "finding-1",
            "summary": "Run the focused verification command.",
            "status": "OPEN",
            "created_event_id": "review-1",
            "updated_event_id": "review-1",
        }
    ]

    rejected = review(
        decision="approved",
        review_summary="Looks complete",
        rationale="The latest output claims success.",
        new_findings=[],
        finding_updates=[],
    )
    assert rejected["success"] is False
    assert "OPEN" in rejected["error"]

    invalid = review(
        decision="approved",
        review_summary="Verification passed",
        rationale="The focused command now passes.",
        new_findings=[],
        finding_updates=[{"finding_id": "finding-1", "status": "ADDRESSED"}],
        context_updates=[{"task_id": "missing", "context": "explicit handoff"}],
    )
    assert invalid["success"] is False
    assert active.review_findings[0]["status"] == "OPEN"
    assert len(active.reviewer_decisions) == 1
    assert active.task_id not in store._staged_reviewer_decisions

    accepted = review(
        decision="approved",
        review_summary="Verification passed",
        rationale="The focused command now passes.",
        new_findings=[],
        finding_updates=[{"finding_id": "finding-1", "status": "ADDRESSED"}],
        context_updates=[
            {"task_id": future.task_id, "context": "Reuse the verified command."}
        ],
    )
    assert accepted["success"]
    store.commit_staged_reviewer_decision(active.task_id)

    assert active.reviewer_decisions[-1]["event_id"] == "review-2"
    assert active.review_findings[0]["status"] == "ADDRESSED"
    assert "Reuse the verified command" in future.metadata["context"]
    assert future.review_findings == []


def test_review_digest_is_bounded_but_older_event_remains_inspectable() -> None:
    store = TaskStateStore()
    task = store.create_task("Retry repeatedly")
    store.record_result(task.task_id, TaskResult(content="attempt"))
    for number in range(10):
        store.record_reviewer_decision(
            task.task_id,
            ReviewerDecision.NEEDS_REVISION,
            rationale=f"Full rationale {number}",
            metadata={
                "review_summary": f"Summary {number}",
                "new_findings": [f"Finding {number}"],
            },
        )

    digest = store.review_journal_digest(task.task_id)

    assert len(digest["open_findings"]) == 8
    assert len(digest["recent_events"]) == 3
    assert digest["recent_events"][0]["event_id"] == "review-8"
    assert store.review_event_detail(task.task_id, "review-1")["rationale"] == (
        "Full rationale 0"
    )


def test_review_finding_rejects_oversized_summary() -> None:
    store = TaskStateStore()
    task = store.create_task("Task")
    store.record_result(task.task_id, TaskResult(content="result", success=False))

    with pytest.raises(ValueError, match="240"):
        store.record_reviewer_decision(
            task.task_id,
            ReviewerDecision.NEEDS_REVISION,
            rationale="Review.",
            metadata={"new_findings": ["x" * 241]},
        )


def test_task_inspect_defaults_to_digest_and_drills_into_one_event() -> None:
    store = TaskStateStore()
    task = store.create_task("Active")
    store.record_result(task.task_id, TaskResult(content="attempt"))
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="Full private rationale for this task only.",
        metadata={
            "review_summary": "Concise retry summary",
            "new_findings": ["Verify the generated file."],
            "finding_updates": [],
            "context_updates": [],
        },
    )
    inspect = TaskInspectTool()
    inspect.bind_task_store(store)

    detail = inspect(task_id=task.task_id)
    event = inspect(task_id=task.task_id, event_id="review-1")

    assert detail["review_journal"]["recent_events"][0]["event_id"] == "review-1"
    assert "Full private rationale" not in str(detail)
    assert event["rationale"] == "Full private rationale for this task only."
    assert event["event_id"] == "review-1"


def test_postponed_journal_resumes_on_same_task_without_sibling_leakage() -> None:
    session = Session()
    store = session.task_store
    root = store.create_task("Roadmap")
    first = store.create_task("Task A", parent_id=root.task_id)
    second = store.create_task("Task B", parent_id=root.task_id)
    store.record_result(
        first.task_id,
        TaskResult(content="TASK_A_RESULT_SECRET", success=False),
    )
    store.record_reviewer_decision(
        first.task_id,
        ReviewerDecision.POSTPONE_SIBLINGS,
        rationale="TASK_A_FULL_RATIONALE",
        metadata={
            "review_summary": "TASK_A_EVENT_SUMMARY",
            "new_findings": ["TASK_A_OPEN_FINDING"],
            "finding_updates": [],
            "context_updates": [],
        },
    )
    store.record_result(second.task_id, TaskResult(content="Task B result"))

    executor = TinyCUATaskExecutorNode(
        "task_executor", create_node_config("task_executor")
    )
    reviewer = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    reviewer.ensure_session(session)
    sibling_prompts = "\n".join(
        [executor.build_continuation(session), reviewer.build_continuation(session)]
    )

    assert "Task A" in sibling_prompts
    assert "postponed" in sibling_prompts
    assert "TASK_A_RESULT_SECRET" not in sibling_prompts
    assert "TASK_A_EVENT_SUMMARY" not in sibling_prompts
    assert "TASK_A_FULL_RATIONALE" not in sibling_prompts
    assert "TASK_A_OPEN_FINDING" not in sibling_prompts

    store.record_reviewer_decision(
        second.task_id,
        ReviewerDecision.APPROVED,
        rationale="Task B passed.",
        metadata={"review_summary": "Task B approved"},
    )
    resumed_prompt = executor.build_continuation(session)

    assert store.active_task_id == first.task_id
    assert "TASK_A_EVENT_SUMMARY" in resumed_prompt
    assert "TASK_A_OPEN_FINDING" in resumed_prompt
    assert "TASK_A_FULL_RATIONALE" not in resumed_prompt
