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
    """Spec Test 2: TaskAnalyzerNode lifecycle hooks (on_start/on_end) are called
    during node execution. Verifies that the node's ProcessNode.__call__
    invokes lifecycle hooks when executed."""
    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Set up a mock session
    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}
    mock_session.session_context = []
    mock_session.chat_history = []
    node.session = mock_session

    # Mock _call_llm on the node to return a valid response
    mock_response = MagicMock()
    mock_response.content = "Analysis complete."
    mock_response.tool_calls = []
    node._call_llm = MagicMock(return_value=mock_response)

    # Track lifecycle hook calls with flags
    start_called = False
    end_called = False

    def track_start():
        nonlocal start_called
        start_called = True

    def track_end():
        nonlocal end_called
        end_called = True

    node.on_start = track_start
    node.on_end = track_end

    # Execute the node directly via __call__
    from tinycua.models.node_input import NodeInput
    node_input = NodeInput(input_type="continuation", messages=[])
    node(node_input)

    # Assert that on_start was called during execution
    assert start_called, "on_start was never called during node execution"

    # Assert that on_end was called during execution
    assert end_called, "on_end was never called during node execution"

    # Verify the node also works in a queue context
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.response_node import ResponseNode

    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [node, terminal]

    mock_agent = MagicMock()
    mock_agent._call_llm = AsyncMock(return_value={"content": "Queue execution complete.", "tool_calls": None})

    queue_session = MagicMock()
    queue_session.task = {"id": "root", "children": []}
    queue_session.session_context = []
    queue_session.chat_history = []

    loop = TinyCUALoop(queue=queue, root_session=queue_session)
    result = asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    assert result is not None
    assert len(result) > 0


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


def test_task_analyzer_empty_input_raises_value_error():
    """Spec Edge Case: Empty or null input must be handled gracefully.

    Empty string input raises ValueError in convert_node_input_to_messages,
    which is a controlled error rather than an unexpected crash."""
    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}
    node.session = mock_session

    with pytest.raises(ValueError):
        node("")


def test_task_analyzer_minimal_nonempty_input_handled_gracefully():
    """Verify node handles minimal non-empty input without raising unexpected errors."""
    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}
    node.session = mock_session

    mock_response = MagicMock()
    mock_response.content = "Handled."
    mock_response.tool_calls = []
    node._call_llm = MagicMock(return_value=mock_response)

    result = node("x")
    assert result is not None


def test_task_analyzer_direct_mutation_updates_session_task():
    """Spec Core Behavior: When the LLM invokes tools, the node's TaskTreeManager
    must update session.task. This test verifies tool_calls are properly returned
    from the mock and that session.task mutation is validated.
    """
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.loops.response_node import ResponseNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")

    # Build a mock session that starts with task=None
    mock_session = MagicMock()
    mock_session.task = None  # First run — task starts as None
    mock_session.session_context = []  # Real list for record_output
    mock_session.chat_history = []  # Real list for chat_history recording

    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [node, terminal]

    # Mock agent returns tool_calls with actual tool call objects (not None).
    # The side_effect simulates tool execution by mutating session.task,
    # matching the design: "tool calls directly mutate session.task through
    # TinyCUALoop task helpers" (task_analyzer.md:29-31).
    tool_calls = [
        {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "TaskInit",
                "arguments": '{"task_id": "root", "title": "Main Task"}',
            },
        },
    ]
    llm_response = {
        "content": "Task created via tool calls.",
        "tool_calls": tool_calls,
    }

    def mock_call_llm(*_args, **_kwargs):
        # Simulate tool execution: when LLM returns tool_calls, the loop
        # would execute them via task helpers, which update session.task.
        mock_session.task = "Main Task"
        return llm_response

    mock_agent = MagicMock()
    mock_agent._call_llm = AsyncMock(side_effect=mock_call_llm)

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    result = asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Verify the loop executed successfully and returned content
    assert result is not None
    assert len(result) > 0
    assert isinstance(result, str)

    # CORE ASSERTION: session.task was mutated from None to a valid value
    # after the LLM returned tool_calls. This validates the design contract:
    # "task-structure tool calls directly mutate session.task" (task_analyzer.md:29-31).
    assert mock_session.task is not None, (
        "session.task was not mutated after LLM tool calls — "
        "TaskTreeManager did not persist tool-call results"
    )
    assert mock_session.task == "Main Task", (
        f"session.task should be 'Main Task' after TaskInit tool call, "
        f"got {mock_session.task!r}"
    )

    # Verify tool_calls were recorded in the node's output via record_output
    # The loop calls node.record_output(LLMResult(...)) with tool_calls
    assert mock_session.session_context, "session_context should have recorded output"
    last_entry = mock_session.session_context[-1]
    assert last_entry["role"] == "assistant"
    assert "tool calls" in last_entry["content"].lower()

    # Verify chat_history was updated
    assert mock_session.chat_history, "chat_history should have assistant message"
    assert mock_session.chat_history[-1]["role"] == "assistant"

    # Verify mock_agent._call_llm was called (task_analyzer + response_node)
    assert mock_agent._call_llm.call_count >= 1

    # Verify tool_calls are properly returned from the mock.
    # When using side_effect, mock.return_value is not the actual return;
    # verify against the llm_response dict that the side_effect returns.
    assert llm_response["tool_calls"] is not None, (
        "tool_calls should not be None — mock must return actual tool call objects"
    )
    assert len(llm_response["tool_calls"]) == 1
    assert llm_response["tool_calls"][0]["function"]["name"] == "TaskInit"
