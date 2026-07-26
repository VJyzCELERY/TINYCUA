"""Unit tests for reviewer missing-tool heuristic fix (Milestone 8, FR-053)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.node import ProcessNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


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


class TestMissingToolHeuristic:
    """Required review-decision errors select the decision tool."""

    def test_heuristic_still_returns_task_review_decision_for_other_errors(self):
        loop = TinyCUALoop()
        node = _ReviewerNode(loop.root_session)
        # A different error that genuinely mentions task_review_decision.
        error_text = (
            "result_reviewer must call task_review_decision before terminating."
        )

        result = loop._missing_or_required_tool_name(node, error_text)
        assert result == "task_review_decision"
