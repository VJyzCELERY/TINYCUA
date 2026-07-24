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
from tinycua.config.types import LLMResult, ValidationError
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


def test_reviewer_prompt_does_not_assign_unfinished_task_curation() -> None:
    """Sibling tasks are context, never additional reviewer assignments."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    store.create_task("Second", parent_id=root.task_id)
    store.record_result(first.task_id, TaskResult(content="done", success=True))
    node = _reviewer_node(loop.root_session)

    prompt = node._reviewer_context_blocks(first, loop.root_session)
    contract = get_node_contract("result_reviewer")

    assert "unfinished tasks" not in prompt.lower()
    assert "curate" not in contract.success_criteria.lower()
    assert "task_inspect" not in contract.success_criteria


def test_approval_with_inspect_in_same_batch_is_valid() -> None:
    """Decide + inspect makes reviewer ready, but terminate is still required."""
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

    assert not validation.is_valid
    assert any("terminate" in error for error in validation.errors)


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


def test_result_reviewer_retry_exposes_terminate_without_hiding_update() -> None:
    """Tool availability stays unchanged while the prompt directs termination."""
    loop = TinyCUALoop()
    node = _reviewer_node(loop.root_session)
    retry_tools = loop._tools_for_retry_attempt(
        node,
        node.config.tool_policy.resolve_tools([]),
        "Required review work is complete; optionally call task_update, then terminate.",
    )

    tool_names = {tool.name for tool in retry_tools}

    assert "terminate" in tool_names
    assert "task_update" in tool_names


def test_result_reviewer_terminate_retry_explains_handoff() -> None:
    """Terminate retry should direct immediate return to the runtime."""
    loop = TinyCUALoop()
    node = _reviewer_node(loop.root_session)
    node.progress.lifecycle_phase = LifecyclePhase.TERMINATE
    message = loop._retry_message_for_validation(
        ValidationError(
            "result_reviewer completed its required work; optionally curate "
            "unfinished tasks with task_update, then call terminate."
        ),
        node,
        node.config.tool_policy.resolve_tools([]),
        LLMResult(),
    )

    assert "Call terminate now" in message
    assert "curate" not in message.lower()
    assert "optional" not in message.lower()


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
    test_reviewer_prompt_does_not_assign_unfinished_task_curation()
    test_approval_with_inspect_in_same_batch_is_valid()
    test_result_reviewer_can_terminate_after_decide_and_inspect()
    test_result_reviewer_retry_exposes_terminate_without_hiding_update()
    test_result_reviewer_terminate_retry_explains_handoff()
    test_worker_lifecycle_node_cannot_terminate_before_required_tool()
    test_no_decision_skips_inspect_requirement()
    test_reviewer_surfaces_failure_count_as_soft_context()
    test_reviewer_no_failure_note_below_threshold()
    print("ok")
