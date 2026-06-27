"""FR-2: ResultReviewer may emit at most one task_review_decision per session.

Kills in-session flip-flopping (needs_revision -> approved -> needs_revision)
observed in experiment-4 logs: a single stuck task was reviewed 14 times. The
validator rejects any reviewer response with >1 successful task_review_decision
call; to overturn a prior decision the reviewer must terminate and start a new
session (append-order in reviewer_decisions handles supersession — no schema
field needed).
"""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode, TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop


def _reviewer_node(loop: TinyCUALoop) -> TinyCUAResultReviewerNode:
    """Build a bound result_reviewer node."""
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    node.ensure_session(loop.root_session)
    return node


def _executor_node(loop: TinyCUALoop) -> TinyCUATaskExecutorNode:
    """Build a bound task_executor node (non-reviewer, for the skip test)."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)
    return node


def _llm_result(tool_results: list[dict]) -> LLMResult:
    """Build an LLMResult whose tool_calls carry the given decision entries.

    The single-decision validator reads ``llm_result.tool_calls`` (the current
    response's calls, not the accumulated tool_results) so it isn't fooled by
    retry-prepend accumulation. Each entry is converted to the tool_call shape
    ``{"function": {"name": ...}}`` the validator expects.
    """
    tool_calls = [
        {"type": "function", "function": {"name": item["name"], "arguments": "{}"}}
        for item in tool_results
    ]
    return LLMResult(content="...", tool_calls=tool_calls, metadata={"tool_results": tool_results})


class TestSingleDecisionValidator:
    """FR-2: reviewer may emit at most one task_review_decision per session."""

    def test_two_decisions_rejected(self) -> None:
        """Two successful task_review_decision calls in one session are rejected."""
        loop = TinyCUALoop()
        node = _reviewer_node(loop)
        llm_result = _llm_result(
            [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "decision": "needs_revision",
                        "task_id": "t1",
                    },
                },
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "decision": "approved",
                        "task_id": "t1",
                    },
                },
            ]
        )
        result = loop._validate_result_reviewer_single_decision(node, llm_result)
        assert not result.is_valid
        assert any("at most one" in e.lower() for e in result.errors)

    def test_one_decision_accepted(self) -> None:
        """A single successful task_review_decision call is accepted."""
        loop = TinyCUALoop()
        node = _reviewer_node(loop)
        llm_result = _llm_result(
            [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "decision": "approved",
                        "task_id": "t1",
                    },
                },
            ]
        )
        result = loop._validate_result_reviewer_single_decision(node, llm_result)
        assert result.is_valid

    def test_one_decision_plus_task_update_accepted(self) -> None:
        """task_update is a different tool — does not count toward the limit."""
        loop = TinyCUALoop()
        node = _reviewer_node(loop)
        llm_result = _llm_result(
            [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "decision": "approved",
                        "task_id": "t1",
                    },
                },
                {
                    "name": "task_update",
                    "output": {"success": True, "task_id": "t2"},
                },
            ]
        )
        result = loop._validate_result_reviewer_single_decision(node, llm_result)
        assert result.is_valid

    def test_non_reviewer_node_skipped(self) -> None:
        """The validator only applies to result_reviewer nodes."""
        loop = TinyCUALoop()
        node = _executor_node(loop)
        llm_result = _llm_result(
            [
                {"name": "task_review_decision", "output": {"success": True}},
                {"name": "task_review_decision", "output": {"success": True}},
            ]
        )
        result = loop._validate_result_reviewer_single_decision(node, llm_result)
        assert result.is_valid

    def test_failed_decision_still_counts_as_call(self) -> None:
        """A task_review_decision call counts even if its execution later fails.

        The validator counts tool_calls (the model's decision *attempts*), not
        tool_results (post-execution success). If the model emitted two
        task_review_decision calls in one response, that's flip-flopping
        regardless of whether either execution succeeded.
        """
        loop = TinyCUALoop()
        node = _reviewer_node(loop)
        llm_result = _llm_result(
            [
                {"name": "task_review_decision", "output": {"success": False, "error": "bad"}},
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "decision": "approved",
                        "task_id": "t1",
                    },
                },
            ]
        )
        result = loop._validate_result_reviewer_single_decision(node, llm_result)
        assert not result.is_valid
        assert any("at most one" in e.lower() for e in result.errors)

    def test_no_decision_accepted(self) -> None:
        """Zero decisions is valid — other validators handle the missing-decision case."""
        loop = TinyCUALoop()
        node = _reviewer_node(loop)
        llm_result = _llm_result([{"name": "task_inspect", "output": {"success": True}}])
        result = loop._validate_result_reviewer_single_decision(node, llm_result)
        assert result.is_valid


if __name__ == "__main__":
    # ponytail: self-check — run the validator contracts directly.
    t = TestSingleDecisionValidator()
    t.test_two_decisions_rejected()
    t.test_one_decision_accepted()
    t.test_one_decision_plus_task_update_accepted()
    t.test_non_reviewer_node_skipped()
    t.test_failed_decision_still_counts_as_call()
    t.test_no_decision_accepted()
    print("ok")