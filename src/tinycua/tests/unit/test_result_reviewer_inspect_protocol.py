"""Regression: ResultReviewer decision protocol.

The old must-inspect-BEFORE-decision rule rolled back approvals when the
reviewer decided without first calling task_inspect. The rollback reverted
``completed`` -> ``in_progress`` and reset ``active_task_id``, so
``schedule_after_review`` re-scheduled the executor for the same task forever
(seen in experiment-1/logs/stdout.log).

The current protocol records the decision without rolling it back or asking
the reviewer to curate unrelated roadmap tasks.
"""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node_contract import LifecyclePhase, get_node_contract
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStatus


def _reviewer_node(session) -> TinyCUAResultReviewerNode:
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    node.ensure_session(session)
    return node


def test_approval_without_inspect_is_accepted() -> None:
    """The commit phase accepts an approval without unavailable action tools.

    The lifecycle now separates inspection from review commit, so an approval
    does not request an unavailable inspection call.
    """
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)

    assert first.status == TaskStatus.COMPLETED  # baseline before validation
    assert store.active_task_id == second.task_id

    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="approved",
        metadata={
            "tool_results": [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "task_id": first.task_id,
                        "decision": "approved",
                        "status": "completed",
                    },
                },
            ]
        },
    )

    validation = loop._validate_result_reviewer_inspects_after_decision(node, llm_result)

    assert validation.is_valid
    assert first.status == TaskStatus.COMPLETED
    assert first.reviewer_decisions  # approval still on the audit trail
    assert store.active_task_id == second.task_id  # active advanced, not reset


def test_reviewer_prompt_orders_decision_before_context_only_curation() -> None:
    """Curation is committed atomically and never becomes execution."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    node = _reviewer_node(loop.root_session)

    prompt = node._reviewer_context_blocks(first, loop.root_session)
    contract = get_node_contract("result_reviewer")

    assert "future-task context curation" in prompt.lower()
    assert "commit atomically" in prompt.lower()
    assert "do not review or execute" in prompt.lower()
    assert "task_review_decision" in contract.success_criteria
    assert "context_updates" in contract.success_criteria


def test_approval_with_inspect_in_same_batch_is_valid() -> None:
    """A valid decision needs no terminate turn."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="approved",
        metadata={
            "tool_results": [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "task_id": first.task_id,
                        "decision": "approved",
                        "status": "completed",
                    },
                },
                {"name": "task_inspect", "output": {"tasks": {}}},
            ]
        },
    )

    validation = loop._validate_node_result(node, llm_result)

    assert validation.is_valid


def test_result_reviewer_can_terminate_after_decide_and_inspect() -> None:
    """Reviewer completes only after decision, inspect, and explicit terminate."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="approved",
        metadata={
            "tool_results": [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "task_id": first.task_id,
                        "decision": "approved",
                        "status": "completed",
                    },
                },
                {"name": "task_inspect", "output": {"success": True, "tasks": {}}},
                {"name": "terminate", "output": {"success": True}},
            ]
        },
    )

    validation = loop._validate_node_result(node, llm_result)

    assert validation.is_valid
    assert validation.errors == []


def test_result_reviewer_commit_exposes_only_decision_tool() -> None:
    """Commit cannot replay inspection or mutate sibling tasks directly."""
    loop = TinyCUALoop()
    node = _reviewer_node(loop.root_session)
    commit_tools = loop._phase_tools(
        node,
        node.config.tool_policy.resolve_tools([]),
        LifecyclePhase.COMMIT,
    )

    tool_names = {tool.name for tool in commit_tools}

    assert tool_names == {"task_review_decision"}


def test_result_reviewer_commit_retry_preserves_action_summary() -> None:
    """A commit retry carries prior action evidence instead of replaying action."""
    loop = TinyCUALoop()
    node = _reviewer_node(loop.root_session)
    node.progress.advance_lifecycle(LifecyclePhase.SUMMARY, "Verified tests passed.")
    node.progress.advance_lifecycle(LifecyclePhase.COMMIT)

    message = loop._lifecycle_phase_directive(node)

    assert "ACTION is complete" in message
    assert "Verified tests passed" in message
    assert "Do not repeat action work" in message
    assert "terminate" not in message


def test_worker_lifecycle_node_cannot_terminate_before_required_tool() -> None:
    """Terminate never bypasses each node's required state tool."""
    loop = TinyCUALoop()
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="done",
        metadata={"tool_results": [{"name": "terminate", "output": {"success": True}}]},
    )

    validation = loop._validate_node_result(node, llm_result)

    assert not validation.is_valid
    assert any("task_review_decision" in error for error in validation.errors)


def test_no_decision_skips_inspect_requirement() -> None:
    """A verify-only batch (no decision yet) is not flagged by this validator.

    ``_validate_tool_owned_task_state`` owns the "must call task_review_decision"
    requirement; this validator only fires once a decision is recorded.
    """
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="verifying",
        metadata={
            "tool_results": [
                {"name": "read_file", "output": {"success": True, "path": "app.py"}},
            ]
        },
    )

    validation = loop._validate_result_reviewer_inspects_after_decision(node, llm_result)

    assert validation.is_valid


def test_reviewer_surfaces_failure_count_as_soft_context() -> None:
    """FR-021: a task sent back 5+ times gets a soft 'consider replan' note.

    The reviewer still LLM-decides — the note is context, not a forced
    decision. Below 5 failures, no note appears.
    """
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))

    # Simulate 5 send-backs (needs_revision) so failure_count == 5.
    for _ in range(5):
        store.record_reviewer_decision(first.task_id, ReviewerDecision.NEEDS_REVISION)

    node = _reviewer_node(loop.root_session)
    continuation = node.build_continuation(loop.root_session)

    assert "5 times" in continuation
    assert "replan" in continuation.lower()
    # The note is soft context, not a forced action-phase commit instruction.
    assert "task_review_decision" not in node.build_instruction()


def test_reviewer_no_failure_note_below_threshold() -> None:
    """Below 5 failures, the reviewer continuation carries no failure note."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    store.record_reviewer_decision(first.task_id, ReviewerDecision.NEEDS_REVISION)

    node = _reviewer_node(loop.root_session)
    continuation = node.build_continuation(loop.root_session)

    assert "times" not in continuation  # no soft note at failure_count=1


if __name__ == "__main__":
    # ponytail: self-check — run the contracts directly.
    test_approval_without_inspect_is_accepted()
    test_reviewer_prompt_orders_decision_before_context_only_curation()
    test_approval_with_inspect_in_same_batch_is_valid()
    test_result_reviewer_can_terminate_after_decide_and_inspect()
    test_result_reviewer_commit_exposes_only_decision_tool()
    test_result_reviewer_commit_retry_preserves_action_summary()
    test_worker_lifecycle_node_cannot_terminate_before_required_tool()
    test_no_decision_skips_inspect_requirement()
    test_reviewer_surfaces_failure_count_as_soft_context()
    test_reviewer_no_failure_note_below_threshold()
    print("ok")
