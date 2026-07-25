"""Tests for Phase 1+2: contract-driven validation, session-persisted progress, goal injection (FR-061..FR-066)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node_contract import (
    ANY_OF_TOOLS_BY_NODE,
    RECOVERY_CHAINS,
    RECOVERY_TOOL_MAP,
    REQUIRED_TOOLS_BY_NODE,
    TERMINATED_NODE_IDS,
    NodeProgress,
    get_node_contract,
)
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode, TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop


class TestContractDerivedMaps:
    """FR-061: runtime maps are derived from _NODE_CONTRACTS."""

    def test_terminated_node_ids_matches_contract(self):
        expected = {
            "task_create",
            "task_analyzer",
            "task_assessor",
            "task_executor",
            "result_reviewer",
        }
        assert TERMINATED_NODE_IDS == expected

    def test_required_tools_by_node_matches_contract(self):
        assert REQUIRED_TOOLS_BY_NODE["task_create"] == frozenset({"task_init"})
        assert REQUIRED_TOOLS_BY_NODE["task_executor"] == frozenset(
            {"task_result_update"}
        )
        assert REQUIRED_TOOLS_BY_NODE["result_reviewer"] == frozenset(
            {"task_review_decision"}
        )

    def test_any_of_tools_by_node_matches_contract(self):
        analyzer = ANY_OF_TOOLS_BY_NODE["task_analyzer"]
        assert frozenset({"task_decompose"}) in analyzer
        assert frozenset({"task_update"}) in analyzer

    def test_recovery_chains_match_expected(self):
        assert RECOVERY_CHAINS["task_create"] == ("task_init",)
        assert RECOVERY_CHAINS["task_analyzer"] == ("task_decompose",)
        assert RECOVERY_CHAINS["result_reviewer"] == ("task_review_decision",)

    def test_recovery_tool_map_includes_alternatives(self):
        # Analyzer's tool map includes both task_decompose AND task_update.
        analyzer_map = RECOVERY_TOOL_MAP["task_analyzer"]
        assert "task_decompose" in analyzer_map
        assert "task_update" in analyzer_map


class TestNodeProgressOnSession:
    """FR-062: NodeProgress lives on session.node_progress[node_id]."""

    def test_progress_persists_on_session(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        # Mark a tool as satisfied.
        node.progress.mark_tool_called("task_decompose", success=True)
        # Progress is stored on the session, not the node instance.
        assert "task_analyzer" in loop.root_session.node_progress
        assert (
            "task_decompose"
            in loop.root_session.node_progress["task_analyzer"].satisfied_requirements
        )

    def test_progress_survives_node_reconstruction(self):
        loop = TinyCUALoop()
        node1 = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node1.ensure_session(loop.root_session)
        node1.progress.mark_tool_called("task_decompose", success=True)
        # Simulate reconstruction — fresh node, same session.
        node2 = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node2.ensure_session(loop.root_session)
        # Progress is preserved because it lives on the session.
        assert "task_decompose" in node2.progress.satisfied_requirements

    def test_progress_cleaned_up_on_completion(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        node.progress.mark_tool_called("task_decompose", success=True)
        assert "task_analyzer" in loop.root_session.node_progress
        # Simulate cleanup (as done in _finalize_node_success).
        loop.root_session.node_progress.pop("task_analyzer", None)
        assert "task_analyzer" not in loop.root_session.node_progress

    def test_progress_fallback_without_session(self):
        """Nodes without a session use instance-level fallback."""
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        # No ensure_session — session is None.
        node.progress.mark_tool_called("task_decompose", success=True)
        assert "task_decompose" in node.progress.satisfied_requirements


class TestNodeProgressAccumulatedResults:
    """FR-063: accumulated_tool_results persists across recovery re-entries."""

    def test_accumulated_tool_results_field_exists(self):
        progress = NodeProgress()
        assert progress.accumulated_tool_results == {}
        assert progress.stage_tool_history == []

    def test_reset_clears_accumulated(self):
        progress = NodeProgress()
        progress.accumulated_tool_results["task_decompose"] = {"success": True}
        progress.stage_tool_history.append({"stage": "test"})
        progress.reset()
        assert progress.accumulated_tool_results == {}
        assert progress.stage_tool_history == []


class TestGoalInjectionInSystemMessage:
    """FR-064: system message contains goal + success criteria + tool rationale."""

    def test_system_message_contains_goal(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        system_msg = node.build_system_message()
        content = system_msg.get("content", "")
        assert "## Your Goal" in content
        assert "Break down the active task" in content

    def test_system_message_contains_role_boundary(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        content = node.build_system_message().get("content", "")

        assert "## Role Boundary" in content
        assert "Do not execute" in content

    def test_system_message_contains_success_criteria(self):
        loop = TinyCUALoop()
        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.ensure_session(loop.root_session)
        system_msg = node.build_system_message()
        content = system_msg.get("content", "")
        assert "## Success Criteria" in content
        assert "task_result_update" in content

    def test_system_message_contains_tool_rationale(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        system_msg = node.build_system_message()
        content = system_msg.get("content", "")
        assert "## Required Tools" in content
        assert "task_decompose" in content
        assert "Creates child tasks" in content


class TestProgressBlockInContinuation:
    """FR-065: continuation injects progress block when satisfied_requirements is non-empty."""

    def test_progress_block_empty_when_no_progress(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        # No tools called yet — progress block should be empty.
        block = node.build_progress_block()
        assert block == ""

    def test_progress_block_shows_satisfied_and_missing(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        node.progress.mark_tool_called("task_decompose", success=True)
        block = node.build_progress_block()
        assert "## Your Progress" in block
        assert "task_decompose" in block
        assert "terminate" in block
        assert "1 step" in block

    def test_progress_block_in_continuation(self):
        loop = TinyCUALoop()
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        node.progress.mark_tool_called("task_decompose", success=True)
        continuation = node.build_continuation(loop.root_session)
        assert "## Your Progress" in continuation


class TestRecoveryMessagesAreGoalOriented:
    """FR-066: recovery messages contain goal + progress + why-missing."""

    def test_recovery_message_contains_goal(self):
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Root")
        store.active_task_id = root.task_id

        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        from tinycua.tools.task_tools import TaskDecomposeTool

        decompose_tool = TaskDecomposeTool()
        decompose_tool._store = store

        llm_result = LLMResult(
            content="I need to decompose", metadata={"tool_results": []}
        )
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "task_analyzer must call at least one successful task-state tool from ['task_decompose', 'task_update']; task state cannot be inferred from prose."
            ],
        )
        messages = loop._build_recovery_messages(
            node,
            [decompose_tool],
            llm_result,
            validation,
            ["task_decompose", "terminate"],
        )
        # The last message is the directive — should contain the goal.
        directive = messages[-1].get("content", "")
        assert "## Node Goal" in directive
        assert "Break down the active task" in directive

    def test_recovery_message_contains_why_missing(self):
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Root")
        store.active_task_id = root.task_id

        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        from tinycua.tools.task_tools import TaskDecomposeTool

        decompose_tool = TaskDecomposeTool()
        decompose_tool._store = store

        llm_result = LLMResult(
            content="I need to decompose", metadata={"tool_results": []}
        )
        validation = ValidationResult(
            is_valid=False,
            errors=["task_analyzer must call at least one successful task-state tool"],
        )
        messages = loop._build_recovery_messages(
            node,
            [decompose_tool],
            llm_result,
            validation,
            ["task_decompose", "terminate"],
        )
        directive = messages[-1].get("content", "")
        assert "## Why task_decompose Is Required" in directive
        assert "Creates child tasks" in directive


class TestContractGoalFields:
    """FR-064: NodeContract has goal, success_criteria, tool_rationale."""

    def test_analyzer_contract_has_goal(self):
        contract = get_node_contract("task_analyzer")
        assert "Break down" in contract.goal
        assert "supported task mutation" in contract.success_criteria
        assert "task_decompose" in contract.tool_rationale
        assert len(contract.tool_rationale["task_decompose"]) > 10

    def test_executor_contract_has_goal(self):
        contract = get_node_contract("task_executor")
        assert "Execute the active task" in contract.goal
        assert "task_result_update" in contract.tool_rationale

    def test_reviewer_contract_has_goal(self):
        contract = get_node_contract("result_reviewer")
        assert "Review" in contract.goal
        assert "task_review_decision" in contract.tool_rationale
        assert "task_inspect" in contract.tool_rationale
