"""Unit tests for reviewer missing-tool heuristic fix (Milestone 8, FR-053)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node import ProcessNode
from tinycua.loops.prompt_protocol_mixin import PromptProtocolMixin
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


class _ReviewerNode(ProcessNode):
    """Minimal reviewer node for heuristic tests."""

    def __init__(self, session: Session) -> None:
        super().__init__(
            "result_reviewer",
            create_node_config("result_reviewer"),
            instruction="test",
            continuation="test",
        )
        self.session = session


class TestInspectAfterDecisionError:
    """The inspect-after-decision error mentions task_inspect, not task_review_decision."""

    def test_error_contains_task_inspect_not_task_review_decision(self):
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="ok"))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        node = _ReviewerNode(loop.root_session)
        llm_result = LLMResult(
            content="approved",
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "output": {"success": True, "decision": "approved"},
                    }
                ]
            },
        )

        validation = loop._validate_result_reviewer_inspects_after_decision(node, llm_result)

        assert not validation.is_valid
        error_text = " ".join(validation.errors)
        # FR-053: the error MUST mention task_inspect (the actually-missing tool)...
        assert "task_inspect" in error_text
        # ...and MUST NOT contain the substring "task_review_decision" (which
        # causes the _missing_or_required_tool_name heuristic to misfire).
        assert "task_review_decision" not in error_text


class TestMissingToolHeuristic:
    """_missing_or_required_tool_name returns task_inspect for the inspect error."""

    def test_heuristic_returns_task_inspect_for_inspect_error(self):
        loop = TinyCUALoop()
        node = _ReviewerNode(loop.root_session)
        # The rephrased error (no "task_review_decision" substring).
        error_text = (
            "ResultReviewer must call task_inspect after the review decision "
            "is recorded. The decision is recorded; now inspect the roadmap."
        )

        # _missing_or_required_tool_name is a method on the loop (PromptProtocolMixin).
        result = loop._missing_or_required_tool_name(node, error_text)
        # FR-053: the heuristic should return task_inspect, not task_review_decision.
        assert result == "task_inspect"

    def test_heuristic_still_returns_task_review_decision_for_other_errors(self):
        loop = TinyCUALoop()
        node = _ReviewerNode(loop.root_session)
        # A different error that genuinely mentions task_review_decision.
        error_text = "result_reviewer must call task_review_decision before terminating."

        result = loop._missing_or_required_tool_name(node, error_text)
        assert result == "task_review_decision"