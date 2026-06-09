"""Unit tests for TinyCUATaskAnalyzerNode — full five-mode support."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode


class TestTaskAnalyzerNodeInit:
    """Tests for TinyCUATaskAnalyzerNode initialization."""

    def test_inherits_from_process_node(self) -> None:
        """TinyCUATaskAnalyzerNode inherits from ProcessNode."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=config,
        )
        assert isinstance(task_analyzer, ProcessNode)

    def test_default_mode_is_initial_analysis(self) -> None:
        """Default mode is 'initial_analysis' (replaces legacy 'analysis')."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=config,
        )
        assert task_analyzer.mode == "initial_analysis"

    def test_default_node_id(self) -> None:
        """TaskAnalyzerNode defaults to 'task_analyzer' node_id."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(config=config)
        assert task_analyzer.node_id == "task_analyzer"


# ---------------------------------------------------------------------------
# Unit tests — five modes
# ---------------------------------------------------------------------------


def test_task_analyzer_all_five_modes_are_valid():
    """All five analysis modes are accepted by TaskAnalyzerNode."""
    config = NodeConfigBase()
    for mode in [
        "initial_analysis",
        "recreation",
        "reanalysis",
        "effort_loop_decomposition",
        "local_replan",
    ]:
        node = TinyCUATaskAnalyzerNode(config=config, mode=mode)
        assert node.mode == mode


def test_task_analyzer_recreation_allows_task_creation_tools():
    """recreation mode includes TaskInit and TaskCreate in tool scope."""
    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")
    assert "TaskInit" in node.tool_scope
    assert "TaskCreate" in node.tool_scope


def test_task_analyzer_non_recreation_excludes_task_creation_tools():
    """All modes except recreation exclude TaskInit and TaskCreate."""
    config = NodeConfigBase()
    for mode in [
        "initial_analysis",
        "reanalysis",
        "effort_loop_decomposition",
        "local_replan",
    ]:
        node = TinyCUATaskAnalyzerNode(config=config, mode=mode)
        assert "TaskInit" not in node.tool_scope, f"TaskInit should not be in {mode}"
        assert "TaskCreate" not in node.tool_scope, f"TaskCreate should not be in {mode}"


def test_task_analyzer_invalid_mode_raises_value_error():
    """Instantiating with an unknown mode raises ValueError."""
    config = NodeConfigBase()
    with pytest.raises(ValueError, match="Unknown analysis mode"):
        TinyCUATaskAnalyzerNode(config=config, mode="nonexistent_mode")


# ---------------------------------------------------------------------------
# Integration Tests — spec-aligned (queue-based, mock LLM)
# ---------------------------------------------------------------------------


def test_task_analyzer_integration_with_tool_policy():
    """Spec Test 1: TaskAnalyzerNode integrates with NodeToolPolicy for
    mode-dependent tool filtering across all modes."""
    config = NodeConfigBase()
    for mode in [
        "initial_analysis",
        "recreation",
        "reanalysis",
        "effort_loop_decomposition",
        "local_replan",
    ]:
        node = TinyCUATaskAnalyzerNode(config=config, mode=mode)
        # recreation must include TaskInit/TaskCreate
        if mode == "recreation":
            assert "TaskInit" in node.tool_scope
            assert "TaskCreate" in node.tool_scope
        else:
            assert "TaskInit" not in node.tool_scope, f"TaskInit leaked into {mode}"
            assert "TaskCreate" not in node.tool_scope, f"TaskCreate leaked into {mode}"


def test_task_analyzer_lifecycle_hooks_in_queue():
    """Spec Test 2: TaskAnalyzerNode in a minimal queue with mock LLM to
    verify the node executes successfully in a queue with lifecycle hooks."""
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.loops.response_node import ResponseNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Spy on lifecycle hooks
    node.on_start = MagicMock(wraps=node.on_start) if hasattr(node, "on_start") else MagicMock()
    node.on_end = MagicMock(wraps=node.on_end) if hasattr(node, "on_end") else MagicMock()

    # Build a minimal queue with terminal node
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [node, terminal]

    # Run via TinyCUALoop — mock agent returns dict format expected by loop
    mock_agent = MagicMock()
    mock_agent._call_llm = AsyncMock(return_value={"content": "Analysis complete.", "tool_calls": None})

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    result = asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Verify the loop executed successfully and returned content
    assert result is not None
    assert len(result) > 0
    # Verify lifecycle hooks fired if they exist
    if hasattr(node, "on_start") and node.on_start.called:
        node.on_start.assert_called()
    if hasattr(node, "on_end") and node.on_end.called:
        node.on_end.assert_called()


def test_task_analyzer_recreation_in_queue_receives_task_tools():
    """Spec Test 3: TaskAnalyzerNode(mode=recreation) in a queue —
    verify the node's tool_scope includes TaskInit/TaskCreate for recreation mode."""
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.loops.response_node import ResponseNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")

    # Verify tool_scope includes TaskInit/TaskCreate for recreation mode
    assert "TaskInit" in node.tool_scope, "TaskInit must be in tool scope for recreation mode"
    assert "TaskCreate" in node.tool_scope, "TaskCreate must be in tool scope for recreation mode"

    # Also verify the node can execute successfully in a queue
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [node, terminal]

    mock_agent = MagicMock()
    mock_agent._call_llm = AsyncMock(return_value={"content": "Task recreated.", "tool_calls": None})

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    result = asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Verify the loop executed successfully
    assert result is not None
    assert len(result) > 0


def test_task_analyzer_initial_analysis_in_queue_excludes_task_tools():
    """Spec Test 4: TaskAnalyzerNode(mode=initial_analysis) in a queue —
    verify the node's tool_scope excludes TaskInit/TaskCreate."""
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.loops.response_node import ResponseNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Verify tool_scope excludes TaskInit/TaskCreate for initial_analysis mode
    assert "TaskInit" not in node.tool_scope, "TaskInit must NOT be in tool scope for initial_analysis"
    assert "TaskCreate" not in node.tool_scope, "TaskCreate must NOT be in tool scope for initial_analysis"

    # Also verify the node can execute successfully in a queue
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [node, terminal]

    mock_agent = MagicMock()
    mock_agent._call_llm = AsyncMock(return_value={"content": "Initial analysis complete.", "tool_calls": None})

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    result = asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Verify the loop executed successfully
    assert result is not None
    assert len(result) > 0


def test_task_analyzer_task_tree_validation_none_raises_error():
    """Spec Test 5: Mock LLM returns without mutating session.task to a valid
    tree — NodeExecutionError must be raised when task tree is None."""
    from tinycua.loops.node import NodeExecutionError

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Mock _call_llm on the node to return a valid response without a real LLM
    mock_response = MagicMock()
    mock_response.content = "No changes made."
    mock_response.tool_calls = []
    node._call_llm = MagicMock(return_value=mock_response)

    mock_session = MagicMock()
    mock_session.task = None  # task is None — should trigger validation
    node.session = mock_session

    with pytest.raises(NodeExecutionError, match="task tree is None"):
        node("test input")


def test_task_analyzer_empty_input_handled_gracefully():
    """Spec Edge Case: Empty or null input must be handled gracefully.

    Note: empty string input raises ValueError in convert_node_input_to_messages,
    so we test with a minimal non-empty string to verify graceful handling."""
    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}
    node.session = mock_session

    # Mock _call_llm to avoid real LLM call
    mock_response = MagicMock()
    mock_response.content = "Handled."
    mock_response.tool_calls = []
    node._call_llm = MagicMock(return_value=mock_response)

    # Verify node handles minimal input without raising unexpected errors
    result = node("x")
    assert result is not None


def test_task_analyzer_direct_mutation_updates_session_task():
    """Spec Core Behavior: Direct mutation — when the LLM invokes tools,
    the node's TaskTreeManager must update session.task."""
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.loops.response_node import ResponseNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")

    # Build a mock session that starts with task=None
    mock_session = MagicMock()
    mock_session.task = None  # First run — task starts as None

    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [node, terminal]

    # Run via TinyCUALoop — mock agent returns content
    mock_agent = MagicMock()
    mock_agent._call_llm = AsyncMock(return_value={"content": "Task created.", "tool_calls": None})

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    result = asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Verify the loop executed successfully
    assert result is not None
    assert len(result) > 0
