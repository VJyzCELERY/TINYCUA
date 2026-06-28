"""Unit tests for NodeState observability in the execution trace."""

from __future__ import annotations

from tinycua.loops.node_contract import NodeProgress, NodeState


class TestNodeProgressTraceIntegration:
    """NodeProgress transitions are observable and structured."""

    def test_transition_records_from_to_reason_attempt(self):
        progress = NodeProgress()
        progress.attempt_count = 2
        progress.transition(NodeState.RETRYING, "schema invalid")
        entry = progress.history[-1]
        assert entry["from"] == NodeState.PENDING
        assert entry["to"] == NodeState.RETRYING
        assert entry["reason"] == "schema invalid"
        assert entry["attempt"] == 2

    def test_visited_tools_track_all_calls(self):
        progress = NodeProgress()
        progress.mark_tool_called("task_result_update", success=True)
        progress.mark_tool_called("read_file", success=True)
        progress.mark_tool_called("run_shell", success=False)
        assert progress.visited_tools == {"task_result_update", "read_file", "run_shell"}
        # Only successful calls are in satisfied_requirements
        assert progress.satisfied_requirements == {"task_result_update", "read_file"}
        assert "run_shell" not in progress.satisfied_requirements

    def test_history_preserves_order(self):
        progress = NodeProgress()
        progress.transition(NodeState.EXECUTING, "start")
        progress.transition(NodeState.AWAITING_TOOL, "tool called")
        progress.transition(NodeState.RETRYING, "validation failed")
        assert len(progress.history) == 3
        assert progress.history[0]["to"] == NodeState.EXECUTING
        assert progress.history[1]["to"] == NodeState.AWAITING_TOOL
        assert progress.history[2]["to"] == NodeState.RETRYING

    def test_phase_reflects_latest_transition(self):
        progress = NodeProgress()
        progress.transition(NodeState.EXECUTING)
        progress.transition(NodeState.COMPLETED)
        assert progress.phase == NodeState.COMPLETED
        assert len(progress.history) == 2
