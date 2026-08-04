"""Task-local execution review journal and context isolation contracts."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.loops.reviewer_protocol import commit_staged_review
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.artifact_history import SessionArtifactStore
from tinycua.models.review_protocol import cumulative_progress_entries
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


def test_review_summary_is_stored_without_length_limit() -> None:
    """Comprehensive review text is durable while finding labels stay bounded."""
    store = TaskStateStore()
    task = store.create_task("Task")
    store.record_result(task.task_id, TaskResult(content="result", success=False))
    summary = "Detailed review section.\n" * 100

    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="Comprehensive rationale.",
        metadata={
            "review_summary": summary,
            "new_findings": ["The result needs revision."],
        },
    )

    assert task.reviewer_decisions[-1]["review_summary"] == summary.strip()
    schema = TaskReviewDecisionTool().parameters["properties"]["review_summary"]
    assert "maxLength" not in schema


def test_needs_revision_requires_an_actionable_open_finding() -> None:
    """Runtime review retries must identify the active defect explicitly."""
    store = TaskStateStore()
    task = store.create_task("Task")
    store.record_result(task.task_id, TaskResult(content="result", success=False))
    review = _review_tool(store)

    rejected = review(
        decision="needs_revision",
        rationale="Something failed.",
        review_summary="The result is incomplete.",
    )
    accepted = review(
        decision="needs_revision",
        rationale="The exact file is missing.",
        review_summary="A required file is missing.",
        new_findings=["Create the exact required file."],
    )

    assert rejected["success"] is False
    assert "OPEN finding" in rejected["error"]
    assert accepted["success"] is True

    with pytest.raises(ValueError, match="OPEN finding"):
        store.record_reviewer_decision(
            task.task_id,
            ReviewerDecision.NEEDS_REVISION,
            rationale="Direct state calls obey the same invariant.",
        )


def test_task_inspect_defaults_to_digest_and_drills_into_one_event() -> None:
    store = TaskStateStore()
    task = store.create_task("Active")
    store.record_result(task.task_id, TaskResult(content="attempt"))
    summary = "Comprehensive retry analysis. " * 30
    rationale = "Full private rationale for this task only. " * 30
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale=rationale,
        metadata={
            "review_summary": summary,
            "new_findings": ["Verify the generated file."],
            "finding_updates": [],
            "context_updates": [],
        },
    )
    inspect = TaskInspectTool()
    inspect.bind_task_store(store)

    detail = inspect(task_id=task.task_id)
    event = inspect(task_id=task.task_id, event_id="review-1")
    pages = []
    offset = 0
    while True:
        page = inspect(
            task_id=task.task_id,
            event_id="review-1",
            field="review_summary",
            offset=offset,
            limit=97,
        )
        pages.append(page["content"])
        if not page["has_more"]:
            break
        offset = page["next_offset"]

    assert detail["review_journal"]["recent_events"][0]["event_id"] == "review-1"
    digest_event = detail["review_journal"]["recent_events"][0]
    assert digest_event["review_summary"] == f"{summary.strip()[:237]}..."
    assert digest_event["review_summary_truncated"] is True
    assert digest_event["review_summary_total_chars"] == len(summary.strip())
    assert rationale.strip() not in str(detail)
    assert event["review_summary"] == summary.strip()
    assert event["rationale"] == rationale
    assert event["event_id"] == "review-1"
    assert "".join(pages) == summary.strip()


@pytest.mark.parametrize(
    "arguments,error",
    [
        ({"field": "review_summary"}, "event_id"),
        ({"event_id": "review-1", "offset": 1}, "field"),
        (
            {"event_id": "review-1", "field": "unknown"},
            "review_summary or rationale",
        ),
        (
            {"event_id": "review-1", "field": "rationale", "limit": 8001},
            "between 1 and 8000",
        ),
    ],
)
def test_task_inspect_rejects_invalid_review_page_requests(
    arguments: dict, error: str
) -> None:
    """Review pagination validates navigation arguments at the tool boundary."""
    store = TaskStateStore()
    task = store.create_task("Active")
    store.record_result(task.task_id, TaskResult(content="attempt"))
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="Full rationale.",
        metadata={"new_findings": ["The result needs revision."]},
    )
    inspect = TaskInspectTool()
    inspect.bind_task_store(store)

    result = inspect(task_id=task.task_id, **arguments)

    assert error in result["error"]


def test_executor_task_inspect_is_active_task_only() -> None:
    """Executor review retrieval cannot bypass task-local context isolation."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    sibling = store.create_task("Sibling", parent_id=root.task_id)
    for task in (active, sibling):
        store.record_result(task.task_id, TaskResult(content="attempt"))
        store.record_reviewer_decision(
            task.task_id,
            ReviewerDecision.NEEDS_REVISION,
            rationale=f"Private rationale for {task.title}.",
            metadata={"new_findings": [f"{task.title} needs revision."]},
        )
    store.active_task_id = active.task_id
    inspect = TaskInspectTool()
    inspect.bind_task_store(store)
    inspect.bind_source_node("task_executor")

    assert (
        inspect(task_id=active.task_id, event_id="review-1")["event_id"] == "review-1"
    )
    assert (
        "active task" in inspect(task_id=sibling.task_id, event_id="review-1")["error"]
    )


def test_executor_deduplicates_rationale_shared_by_open_findings() -> None:
    """One review event is injected once even when it created several findings."""
    session = Session()
    store = session.task_store
    task = store.create_task("Active")
    store.record_result(task.task_id, TaskResult(content="attempt", success=False))
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="SHARED_COMPLETE_RATIONALE",
        metadata={"new_findings": ["FIRST_FINDING", "SECOND_FINDING"]},
    )
    executor = TinyCUATaskExecutorNode(
        "task_executor", create_node_config("task_executor")
    )

    prompt = executor.build_continuation(session)

    assert "FIRST_FINDING" in prompt
    assert "SECOND_FINDING" in prompt
    assert prompt.count("SHARED_COMPLETE_RATIONALE") == 1


def test_reviewer_receives_full_report_and_labeled_executor_evidence() -> None:
    """Reviewer sees the full claim separately from bounded Executor evidence."""
    session = Session()
    store = session.task_store
    task = store.create_task("Verify source")
    url = "https://benchlm.ai/models/" + "frontier-model-" * 40
    report = f"Fetched the complete model profile from {url}"
    store.record_result(
        task.task_id,
        TaskResult(
            content=report,
            metadata={
                "tool_results": [
                    {
                        "name": "fetch_url",
                        "artifact_path": "artifacts/tool-calls/0001-fetch_url.json",
                        "output": {
                            "cache_id": "cache-fetch-1",
                            "captured_at": "2026-08-02T00:00:00+00:00",
                        },
                        "outcome": {
                            "call_id": "executor-call-1",
                            "tool_name": "fetch_url",
                            "success": True,
                            "invocation": {"url": url},
                            "truncated": True,
                        },
                    }
                ]
            },
        ),
    )
    reviewer = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    reviewer.ensure_session(session)

    prompt = reviewer.build_continuation(session)

    assert "## Executor report (primary review target)" in prompt
    assert report in prompt
    assert "## Executor tool-call evidence" in prompt
    assert "not independent Reviewer observations" in prompt
    assert "output_preview_truncated=True" in prompt
    assert f"url={url}" in prompt
    assert "cache_id=cache-fetch-1" in prompt
    assert "load_cache=true" in prompt


def test_reviewer_evidence_bounds_pathological_url_preview() -> None:
    """Runtime provenance keeps the URL while its prompt projection stays bounded."""
    session = Session()
    store = session.task_store
    task = store.create_task("Verify source")
    url = "https://example.test/" + "x" * 250_000
    outcome = {
        "call_id": "executor-call-1",
        "tool_name": "fetch_url",
        "success": True,
        "invocation": {"url": url},
    }
    store.record_result(
        task.task_id,
        TaskResult(
            content="Fetched the model profile.",
            metadata={"tool_results": [{"name": "fetch_url", "outcome": outcome}]},
        ),
    )
    reviewer = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    reviewer.ensure_session(session)

    prompt = reviewer.build_continuation(session)
    evidence_line = next(
        line for line in prompt.splitlines() if line.startswith("- fetch_url:")
    )

    assert outcome["invocation"]["url"] == url
    assert len(evidence_line) <= 3500
    assert "prompt preview truncated" in evidence_line
    assert "total_chars=" in evidence_line
    assert "sha256=" in evidence_line


def test_reviewer_task_inspect_does_not_replace_report_with_silent_preview() -> None:
    """Reviewer detail preserves the report; compact callers get explicit bounds."""
    store = TaskStateStore()
    task = store.create_task("Verify source")
    url = "https://benchlm.ai/models/" + "frontier-model-" * 40
    report = f"Fetched the complete model profile from {url}"
    store.record_result(task.task_id, TaskResult(content=report))
    inspect = TaskInspectTool()
    inspect.bind_task_store(store)

    compact = inspect(task_id=task.task_id)
    inspect.bind_source_node("result_reviewer")
    reviewer_detail = inspect(task_id=task.task_id)

    assert compact["result"]["content"] == report[:200]
    assert compact["result"]["content_truncated"] is True
    assert compact["result"]["content_total_chars"] == len(report)
    assert reviewer_detail["result"]["content"] == report
    assert reviewer_detail["result"]["content_truncated"] is False
    assert reviewer_detail["result"]["content_total_chars"] == len(report)


def test_role_specific_review_context_is_complete_and_relevant() -> None:
    """Executor gets current remediation detail; Reviewer gets the status ledger."""
    session = Session()
    store = session.task_store
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    sibling = store.create_task("Sibling", parent_id=root.task_id)
    store.record_result(active.task_id, TaskResult(content="attempt", success=False))
    store.record_reviewer_decision(
        active.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="ADDRESSED_RATIONALE",
        metadata={
            "review_summary": "ADDRESSED_SUMMARY",
            "new_findings": ["ADDRESSED_FINDING"],
        },
    )
    store.record_reviewer_decision(
        active.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="DEFERRED_RATIONALE",
        metadata={
            "review_summary": "DEFERRED_SUMMARY",
            "new_findings": ["DEFERRED_FINDING"],
            "finding_updates": [{"finding_id": "finding-1", "status": "ADDRESSED"}],
        },
    )
    store.record_reviewer_decision(
        active.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="INVALID_RATIONALE",
        metadata={
            "review_summary": "INVALID_SUMMARY",
            "new_findings": ["INVALID_FINDING"],
            "finding_updates": [{"finding_id": "finding-2", "status": "DEFERRED"}],
        },
    )
    current_rationale = "CURRENT_OPEN_RATIONALE\n" * 600
    store.record_reviewer_decision(
        active.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale=current_rationale,
        metadata={
            "review_summary": "CURRENT_SUMMARY",
            "new_findings": ["CURRENT_OPEN_FINDING"],
            "finding_updates": [{"finding_id": "finding-3", "status": "INVALID"}],
        },
    )
    store.record_result(sibling.task_id, TaskResult(content="SIBLING_RESULT"))
    store.record_reviewer_decision(
        sibling.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="SIBLING_RATIONALE",
        metadata={"new_findings": ["SIBLING_FINDING"]},
    )
    store.active_task_id = active.task_id
    executor = TinyCUATaskExecutorNode(
        "task_executor", create_node_config("task_executor")
    )
    reviewer = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    reviewer.ensure_session(session)

    executor_prompt = executor.build_continuation(session)
    reviewer_prompt = reviewer.build_continuation(session)

    assert "CURRENT_OPEN_FINDING" in executor_prompt
    assert current_rationale.strip() in executor_prompt
    for excluded in (
        "ADDRESSED_FINDING",
        "ADDRESSED_RATIONALE",
        "DEFERRED_FINDING",
        "DEFERRED_RATIONALE",
        "INVALID_FINDING",
        "INVALID_RATIONALE",
        "SIBLING_FINDING",
        "SIBLING_RATIONALE",
    ):
        assert excluded not in executor_prompt
    for finding_id, status, summary in (
        ("finding-1", "ADDRESSED", "ADDRESSED_FINDING"),
        ("finding-2", "DEFERRED", "DEFERRED_FINDING"),
        ("finding-3", "INVALID", "INVALID_FINDING"),
        ("finding-4", "OPEN", "CURRENT_OPEN_FINDING"),
    ):
        assert f"{finding_id} [{status}]" in reviewer_prompt
        assert f"finding_id={finding_id}" in reviewer_prompt
        assert summary in reviewer_prompt
    assert "source_event_id=" in reviewer_prompt
    assert "Use the exact finding_id value" in reviewer_prompt
    assert "CURRENT_OPEN_RATIONALE" not in reviewer_prompt
    assert "SIBLING_FINDING" not in reviewer_prompt


def test_reviewer_finding_update_schema_names_task_local_ids() -> None:
    """Reviewer updates distinguish findings from task, event, and evidence IDs."""
    finding_id = TaskReviewDecisionTool().parameters["properties"]["finding_updates"][
        "items"
    ]["properties"]["finding_id"]

    assert "finding-N" in finding_id["description"]
    assert "event" in finding_id["description"]


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
    assert "TASK_A_EVENT_SUMMARY" not in resumed_prompt
    assert "TASK_A_OPEN_FINDING" in resumed_prompt
    assert "TASK_A_FULL_RATIONALE" in resumed_prompt


# ---------------------------------------------------------------------------
# Cumulative review context and artifact history (local:cumulative-review-artifact-history)
# ---------------------------------------------------------------------------


def test_cumulative_progress_entries_stay_goal_ordered_and_immutable() -> None:
    """Prior committed reviews survive later reviews in goal order."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="first report"))
    store.record_reviewer_decision(
        first.task_id,
        ReviewerDecision.APPROVED,
        rationale="ok",
        metadata={"review_summary": "FIRST APPROVED SUMMARY"},
    )
    store.record_result(second.task_id, TaskResult(content="second report"))
    store.record_reviewer_decision(
        second.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="fix",
        metadata={
            "review_summary": "SECOND REVISION SUMMARY",
            "new_findings": ["fix it"],
        },
    )

    entries = cumulative_progress_entries(store)

    assert [entry["task_id"] for entry in entries] == [first.task_id, second.task_id]
    assert [entry["review_summary"] for entry in entries] == [
        "FIRST APPROVED SUMMARY",
        "SECOND REVISION SUMMARY",
    ]
    assert [entry["decision"] for entry in entries] == ["approved", "needs_revision"]
    assert all(entry["event_id"].startswith("review-") for entry in entries)


def test_replan_retains_prior_progression() -> None:
    """Replanning does not discard the reviews that triggered it."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Stuck", parent_id=root.task_id)
    store.record_result(task.task_id, TaskResult(content="attempt", success=False))
    for number in range(3):
        store.record_reviewer_decision(
            task.task_id,
            ReviewerDecision.NEEDS_REVISION,
            rationale=f"fix {number}",
            metadata={
                "review_summary": f"SUMMARY {number}",
                "new_findings": [f"finding {number}"],
            },
        )
    before = [entry["review_summary"] for entry in cumulative_progress_entries(store)]
    assert before == ["SUMMARY 0", "SUMMARY 1", "SUMMARY 2"]

    # FR-049 replan boundary is inserted directly into the audit trail; the
    # derived progression must keep the reviews that triggered the replan.
    task.reviewer_decisions.append(
        {"decision": "replan_boundary", "rationale": "auto replan", "metadata": {}}
    )
    after = [entry["review_summary"] for entry in cumulative_progress_entries(store)]

    assert after == before


def test_progress_after_replan_boundary_uses_committed_event_identity() -> None:
    """A replan sentinel cannot displace the next committed review event."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Stuck", parent_id=root.task_id)
    store.record_result(task.task_id, TaskResult(content="attempt", success=False))
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="first",
        metadata={"review_summary": "FIRST", "new_findings": ["first"]},
    )
    task.reviewer_decisions.append(
        {"decision": "replan_boundary", "rationale": "replan", "metadata": {}}
    )
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="second",
        metadata={"review_summary": "SECOND", "new_findings": ["second"]},
    )

    assert [
        entry["review_summary"] for entry in cumulative_progress_entries(store)
    ] == [
        "FIRST",
        "SECOND",
    ]


def test_committed_verdict_anchors_exact_result_and_artifact_range() -> None:
    """A committed verdict identifies the exact result hash and revision range."""
    store = TaskStateStore()
    task = store.create_task("Write report")
    store.record_result(task.task_id, TaskResult(content="exact report content"))
    review = _review_tool(store)

    review(decision="approved", review_summary="Looks good", rationale="verified")
    staged = store._staged_reviewer_decisions[task.task_id]
    staged["metadata"]["runtime_result_revision"] = {
        "revision_id": "result-abc123",
        "content_hash": "deadbeef",
        "artifact_range": {"from": "rev-1", "to": "rev-2"},
    }
    store.commit_staged_reviewer_decision(task.task_id)

    event = task.reviewer_decisions[-1]
    assert event["result_revision"] == {
        "revision_id": "result-abc123",
        "content_hash": "deadbeef",
        "artifact_range": {"from": "rev-1", "to": "rev-2"},
    }
    assert task.result_revisions == [
        {"revision_id": "result-abc123", "content_hash": "deadbeef"}
    ]


def test_review_rejects_invalid_runtime_anchor_shape() -> None:
    """Runtime-owned provenance fields are validated at commit time."""
    store = TaskStateStore()
    task = store.create_task("Write report")
    store.record_result(task.task_id, TaskResult(content="report"))
    review = _review_tool(store)

    review(decision="approved", review_summary="ok", rationale="fine")
    staged = store._staged_reviewer_decisions[task.task_id]
    staged["metadata"]["runtime_result_revision"] = {
        "revision_id": "",
        "content_hash": "",
        "artifact_range": {},
    }

    with pytest.raises(ValueError, match="Runtime"):
        store.commit_staged_reviewer_decision(task.task_id)


def test_review_checkpoint_advances_atomically_with_committed_verdict(
    tmp_path,
) -> None:
    """Failed or abandoned attempts never advance the review checkpoint."""
    session = Session()
    session.session_config = SessionConfig(workspace_dir=tmp_path)
    store = session.task_store
    artifact_store = SessionArtifactStore(workspace_dir=tmp_path)
    root = store.create_task("Root")
    first = store.create_task("Write report", parent_id=root.task_id)
    artifact_store.begin_capture()
    (tmp_path / "report.md").write_text("v1")
    artifact_store.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )
    store.record_result(first.task_id, TaskResult(content="report v1"))
    review = _review_tool(store)

    # Abandoned attempt: staged but never committed → checkpoint unchanged.
    review(decision="approved", review_summary="draft", rationale="not final")
    assert artifact_store.checkpoint() is None

    # Committed approval advances the checkpoint to the latest revision.
    review(decision="approved", review_summary="Verified", rationale="checked")
    commit_staged_review(store, artifact_store, first.task_id)

    checkpoint = artifact_store.checkpoint()
    assert checkpoint is not None
    assert checkpoint["revision_id"] == artifact_store.latest_revision_id()
    assert checkpoint["task_id"] == first.task_id
    event = first.reviewer_decisions[-1]
    assert event["result_revision"]["artifact_range"]["to"] == (
        artifact_store.latest_revision_id()
    )

    # A committed needs_revision does not advance the checkpoint.
    second = store.create_task("Update report", parent_id=root.task_id)
    artifact_store.begin_capture()
    (tmp_path / "report.md").write_text("v2")
    artifact_store.finish_capture(
        {"tool_name": "str_replace", "call_id": "c2", "success": True}
    )
    store.record_result(second.task_id, TaskResult(content="report v2"))
    review(
        decision="needs_revision",
        review_summary="more",
        rationale="fix",
        new_findings=["more work"],
    )
    commit_staged_review(store, artifact_store, second.task_id)

    assert artifact_store.checkpoint()["revision_id"] == checkpoint["revision_id"]


def test_reviewer_receives_cumulative_checkpoint_diff_without_raw_paths(
    tmp_path,
) -> None:
    """The next Reviewer sees only the changed paths since the last checkpoint."""
    session = Session()
    session.session_config = SessionConfig(workspace_dir=tmp_path)
    store = session.task_store
    artifact_store = SessionArtifactStore(workspace_dir=tmp_path)
    session.artifact_store = artifact_store
    root = store.create_task("Root")
    first = store.create_task("Write report", parent_id=root.task_id)
    artifact_store.begin_capture()
    (tmp_path / "report.md").write_text("v1")
    artifact_store.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )
    store.record_result(first.task_id, TaskResult(content="report v1"))
    review = _review_tool(store)
    review(decision="approved", review_summary="ok", rationale="fine")
    commit_staged_review(store, artifact_store, first.task_id)

    second = store.create_task("Update report", parent_id=root.task_id)
    artifact_store.begin_capture()
    (tmp_path / "report.md").write_text("v2 with benchmarks")
    artifact_store.finish_capture(
        {"tool_name": "str_replace", "call_id": "c2", "success": True}
    )
    store.record_result(second.task_id, TaskResult(content="report v2"))
    reviewer = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    reviewer.ensure_session(session)

    prompt = reviewer.build_continuation(session)

    assert "Artifacts changed since last review checkpoint" in prompt
    assert "report.md" in prompt
    assert "rev-" in prompt
    assert str(tmp_path.resolve()) not in prompt


def test_incomplete_audit_blocks_review_approval(tmp_path) -> None:
    """Post-mutation persistence failure blocks approval until surfaced."""
    from tinycua.config.session_config import SessionConfig

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = Session()
    session.session_config = SessionConfig(workspace_dir=workspace)
    store = session.task_store
    blocker = tmp_path / "session-store"
    blocker.write_text("not a directory")
    artifact_store = SessionArtifactStore(workspace_dir=workspace, session_dir=blocker)
    task = store.create_task("Write report")
    (workspace / "report.md").write_text("v1")
    artifact_store.begin_capture()
    artifact_store.finish_capture(
        {"tool_name": "write_file", "call_id": "c1", "success": True}
    )
    store.record_result(task.task_id, TaskResult(content="report"))
    review = _review_tool(store)
    review(decision="approved", review_summary="ok", rationale="fine")

    with pytest.raises(ValueError, match="incomplete"):
        commit_staged_review(store, artifact_store, task.task_id)
