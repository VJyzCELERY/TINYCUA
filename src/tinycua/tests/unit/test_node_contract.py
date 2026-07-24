"""Unit tests for NodeContract (single source of truth) and NodeProgress."""

from __future__ import annotations

from tinycua.loops.node_contract import (
    LifecyclePhase,
    NodeProgress,
    NodeState,
    get_node_contract,
    phase_tool_names,
    terminated_node_ids,
)


class TestNodeState:
    """NodeState enum covers the full lifecycle."""

    def test_all_states_present(self):
        states = [s.value for s in NodeState]
        assert "pending" in states
        assert "executing" in states
        assert "awaiting_tool" in states
        assert "retrying" in states
        assert "completed" in states
        assert "failed" in states


class TestNodeProgress:
    """NodeProgress tracks per-node runtime state."""

    def test_defaults(self):
        progress = NodeProgress()
        assert progress.phase == NodeState.PENDING
        assert progress.attempt_count == 0
        assert progress.visited_tools == set()
        assert progress.satisfied_requirements == set()
        assert progress.history == []

    def test_transition_records_history(self):
        progress = NodeProgress()
        progress.transition(NodeState.RETRYING, "schema invalid")
        assert progress.phase == NodeState.RETRYING
        assert len(progress.history) == 1
        assert progress.history[0]["from"] == NodeState.PENDING
        assert progress.history[0]["to"] == NodeState.RETRYING
        assert progress.history[0]["reason"] == "schema invalid"

    def test_mark_tool_called_tracks_visited_and_satisfied(self):
        progress = NodeProgress()
        progress.mark_tool_called("task_result_update", success=True)
        assert "task_result_update" in progress.visited_tools
        assert "task_result_update" in progress.satisfied_requirements

    def test_mark_tool_called_failed_not_satisfied(self):
        progress = NodeProgress()
        progress.mark_tool_called("task_result_update", success=False)
        assert "task_result_update" in progress.visited_tools
        assert "task_result_update" not in progress.satisfied_requirements

    def test_reset_clears_state(self):
        progress = NodeProgress()
        progress.transition(NodeState.EXECUTING)
        progress.attempt_count = 5
        progress.mark_tool_called("task_init")
        progress.reset()
        assert progress.phase == NodeState.PENDING
        assert progress.attempt_count == 0
        assert progress.visited_tools == set()
        assert progress.satisfied_requirements == set()
        assert progress.history == []

    def test_action_summary_transitions_to_isolated_commit_and_termination(self):
        """Lifecycle phases keep action output available without exposing commit tools."""
        progress = NodeProgress()
        progress.advance_lifecycle(LifecyclePhase.SUMMARY, summary="tests passed")
        progress.advance_lifecycle(LifecyclePhase.COMMIT)
        progress.advance_lifecycle(LifecyclePhase.TERMINATE)

        assert progress.action_summary == "tests passed"
        assert [entry["phase"] for entry in progress.lifecycle_history] == [
            "summary",
            "commit",
            "terminate",
        ]


class TestNodeContract:
    """NodeContract declares per-node tool/state requirements."""

    def test_task_executor_contract(self):
        contract = get_node_contract("task_executor")
        assert contract.required_tools == frozenset({"task_result_update"})
        assert contract.requires_terminate is True
        assert contract.early_stop_tool == "task_result_update"
        assert contract.retry_max_attempts == 25
        assert "terminate" in contract.deterministic_tools

    def test_task_create_contract(self):
        contract = get_node_contract("task_create")
        assert contract.required_tools == frozenset({"task_init"})
        assert contract.requires_terminate is True
        assert contract.early_stop_tool == "task_init"

    def test_result_reviewer_contract(self):
        contract = get_node_contract("result_reviewer")
        assert contract.required_tools == frozenset({"task_review_decision"})
        assert contract.requires_terminate is True
        assert contract.retry_max_attempts == 25

    def test_task_analyzer_contract_any_of(self):
        contract = get_node_contract("task_analyzer")
        # Any supported mutation lets the analyzer terminate.
        assert contract.any_of_tools == frozenset({
            frozenset({"task_decompose"}),
            frozenset({"task_update"}),
            frozenset({"task_create"}),
            frozenset({"task_shrink"}),
        })
        assert contract.requires_terminate is True

    def test_task_assessor_contract(self):
        contract = get_node_contract("task_assessor")
        assert contract.required_tools == frozenset({"node_handoff"})
        assert contract.requires_terminate is True
        assert contract.early_stop_tool == "node_handoff"

    def test_query_analyst_contract(self):
        contract = get_node_contract("query_analyst")
        assert contract.required_tools == frozenset({"select_query_route"})
        assert contract.requires_terminate is False
        assert contract.structured_output_schema is None

    def test_worker_contract(self):
        contract = get_node_contract("worker")
        assert contract.required_tools == frozenset({"select_worker_route"})
        assert contract.requires_terminate is False

    def test_unknown_node_gets_empty_contract(self):
        contract = get_node_contract("unknown_node")
        assert contract.required_tools == frozenset()
        assert contract.any_of_tools == frozenset()
        assert contract.requires_terminate is False

    def test_is_satisfied_all_required_present(self):
        contract = get_node_contract("task_executor")
        assert contract.is_satisfied({"task_result_update"})
        assert not contract.is_satisfied(set())

    def test_is_satisfied_any_of_one_group_present(self):
        contract = get_node_contract("task_analyzer")
        assert contract.is_satisfied({"task_decompose"})
        assert contract.is_satisfied({"task_update"})
        assert contract.is_satisfied({"task_create"})
        assert contract.is_satisfied({"task_shrink"})
        assert not contract.is_satisfied(set())
        assert not contract.is_satisfied({"task_init"})

    def test_executor_phase_tools_do_not_expose_finalization_during_action(self):
        """Action, commit, and termination each expose only their own tools."""
        names = {"read_file", "run_shell", "task_result_update", "terminate"}

        assert phase_tool_names("task_executor", names, LifecyclePhase.ACTION) == {
            "read_file",
            "run_shell",
        }
        assert phase_tool_names("task_executor", names, LifecyclePhase.COMMIT) == {
            "task_result_update",
        }
        assert phase_tool_names("task_executor", names, LifecyclePhase.TERMINATE) == {
            "terminate",
        }


class TestTerminatedNodeIds:
    """terminated_node_ids returns the lifecycle-gated set."""

    def test_includes_all_worker_lifecycle_nodes(self):
        ids = terminated_node_ids()
        assert "task_create" in ids
        assert "task_analyzer" in ids
        assert "task_assessor" in ids
        assert "task_executor" in ids
        assert "result_reviewer" in ids

    def test_excludes_non_lifecycle_nodes(self):
        ids = terminated_node_ids()
        assert "query_analyst" not in ids
        assert "worker" not in ids
        assert "response" not in ids
