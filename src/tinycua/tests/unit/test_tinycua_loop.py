"""Tests for TinyCUALoop — node execution, message merging, tool scoping, override, streaming."""

from __future__ import annotations

import collections.abc

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.classification import MandatoryPassthrough
from tinycua.models.session import Session
from tinycua.models.task import Task
from tinycua_sdk.agent import BaseLoop

from tests.mock_llm import MockLLM
from tests.unit.helpers.tinycua_loop_helpers import StubNode, StubResponseNode


# --- Basic construction tests ---


def test_tinycua_loop_extends_base_loop():
    """TinyCUALoop is a subclass of SDK BaseLoop."""
    session = Session()
    loop = TinyCUALoop(root_session=session)
    assert isinstance(loop, BaseLoop)


def test_tinycua_loop_creates_session_by_default():
    """TinyCUALoop creates a Session when none provided."""
    loop = TinyCUALoop()
    assert isinstance(loop.root_session, Session)
    assert loop.root_session.session_id is not None


def test_tinycua_loop_uses_provided_session():
    """TinyCUALoop uses the provided session."""
    session = Session()
    loop = TinyCUALoop(root_session=session)
    assert loop.root_session is session


def test_tinycua_loop_has_node_queue():
    """TinyCUALoop creates a NodeQueue with QueryAnalyst + ResponseNode by default."""
    loop = TinyCUALoop()
    assert isinstance(loop.queue, NodeQueue)
    assert len(loop.queue.items) == 2
    assert loop.queue.items[0].node_id == "query_analyst"
    assert loop.queue.items[1].node_id == "response"
    assert loop.queue.items[1].is_terminal is True


def test_tinycua_loop_stores_session_config():
    """TinyCUALoop stores session_config; factory applies it to session."""
    from tinycua.config.session_config import SessionConfig

    config = SessionConfig(max_context_messages=50)
    loop = TinyCUALoop(session_config=config)
    assert loop.session_config is config
    assert loop.root_session.session_config is None


def test_tinycua_loop_default_max_iterations():
    """TinyCUALoop defaults to 50 max iterations."""
    loop = TinyCUALoop()
    assert loop.max_iterations == 50


def test_tinycua_loop_custom_max_iterations():
    """TinyCUALoop accepts custom max_iterations."""
    loop = TinyCUALoop(max_iterations=10)
    assert loop.max_iterations == 10


# --- _execute_node tests ---


async def test_execute_node_calls_agent_with_node_messages():
    """_execute_node() builds messages from node and calls agent._call_llm()."""
    stub = StubNode("node output")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    await loop.run(
        agent=agent, messages=[], tools=[], override_instructions=None, stream=False,
    )
    agent._call_llm.assert_called()


async def test_execute_node_records_chat_history():
    """_execute_node() appends each node's LLM call to root_session.chat_history."""
    stub = StubNode("history test")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    await loop.run(
        agent=agent, messages=[], tools=[], override_instructions=None, stream=False,
    )
    assert len(session.chat_history) > 0


async def test_execute_node_records_session_context():
    """_execute_node() records session_context via node.record_output()."""
    stub = StubNode("context test")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    await loop.run(
        agent=agent, messages=[], tools=[], override_instructions=None, stream=False,
    )
    assert len(session.session_context) > 0


async def test_execute_node_stops_at_terminal():
    """_execute_node() stops processing when a terminal node is encountered."""
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "final", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent, messages=[], tools=[], override_instructions=None, stream=False,
    )
    assert isinstance(result, str)


# --- message merging tests ---


async def test_message_merging_populates_input_context():
    """run() merges SDK messages into root_session.input_context."""
    stub = StubNode("merge test")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    await loop.run(
        agent=agent, messages=messages, tools=[], override_instructions=None, stream=False,
    )
    assert session.input_context == messages


async def test_message_merging_preserves_order():
    """Merged messages retain their original order."""
    stub = StubNode("order test")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]

    await loop.run(
        agent=agent, messages=messages, tools=[], override_instructions=None, stream=False,
    )
    assert [m["content"] for m in session.input_context] == ["first", "second", "third"]


# --- tool scoping tests ---


async def test_tool_scoping_filters_tools_per_node():
    """NodeToolPolicy.resolve_tools() filters outer tools per node config."""
    policy = NodeToolPolicy(
        include_agent_tools="selected",
        allowed_agent_tool_names=["tool_a"],
    )
    config = NodeConfigBase(tool_policy=policy)
    node = StubNode()
    node.config = config

    tool_a = MagicMock()
    tool_a.name = "tool_a"
    tool_b = MagicMock()
    tool_b.name = "tool_b"
    outer_tools = [tool_a, tool_b]
    resolved = config.tool_policy.resolve_tools(outer_tools)
    assert len(resolved) == 1


async def test_tool_scoping_all_tools():
    """NodeToolPolicy with include_agent_tools='all' passes all tools through."""
    policy = NodeToolPolicy(include_agent_tools="all")
    config = NodeConfigBase(tool_policy=policy)
    node = StubNode()
    node.config = config

    tool_a = MagicMock()
    tool_a.name = "tool_a"
    tool_b = MagicMock()
    tool_b.name = "tool_b"
    outer_tools = [tool_a, tool_b]
    resolved = config.tool_policy.resolve_tools(outer_tools)
    assert len(resolved) == 2


# --- override_instructions tests ---


async def test_override_instructions_passed_to_node():
    """override_instructions reaches node.build_instruction() during message building."""
    stub = StubNode("override test")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "default"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    await loop.run(
        agent=agent, messages=[], tools=[],
        override_instructions="custom instructions", stream=False,
    )
    agent._call_llm.assert_called()


# --- stream tests ---


async def test_stream_false_returns_string():
    """run(stream=False) returns a string response."""
    stub = StubNode("string result")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent, messages=[], tools=[], override_instructions=None, stream=False,
    )
    assert isinstance(result, str)


async def test_stream_true_returns_async_iterator():
    """run(stream=True) returns an async iterator with content deltas."""
    stub = StubNode("streaming response")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    async def mock_stream(*args, **kwargs):
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream

    result = await loop.run(
        agent=agent, messages=[], tools=[], override_instructions=None, stream=True,
    )
    assert isinstance(result, collections.abc.AsyncIterator)
    events = [e async for e in result]
    assert len(events) > 0
    assert any(e["type"] == "response.output_text.delta" for e in events)


# --- Existing passthrough tests (backward compat) ---


async def test_run_records_user_message():
    """run() records user messages in input_context (not chat_history)."""
    stub = StubNode("response")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "Hi", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "hello"}]
    await loop.run(agent, messages, tools=[], stream=False)
    # User messages are stored in input_context, not chat_history
    user_msgs = [m for m in loop.root_session.input_context if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "hello"
    # chat_history should not contain user messages
    chat_user_msgs = [m for m in loop.root_session.chat_history if m["role"] == "user"]
    assert len(chat_user_msgs) == 0


async def test_run_records_assistant_response():
    """run() records assistant response in chat_history."""
    stub = StubNode("response")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "Hello there", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "hi"}]
    await loop.run(agent, messages, tools=[], stream=False)
    assistant_msgs = [m for m in loop.root_session.chat_history if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1]["content"] == "Hello there"


async def test_run_calls_build_system_message_with_override():
    """run() passes override_instructions to node execution via _build_node_messages."""
    stub = StubNode("response")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "test"}]
    with pytest.MonkeyPatch.context() as m:
        original_build = loop._build_node_messages
        called_with = []
        def spy_build(node, override=None):
            called_with.append(override)
            return original_build(node, override)
        m.setattr(loop, "_build_node_messages", spy_build)
        await loop.run(agent, messages, tools=[], override_instructions="custom instructions", stream=False)
    assert "custom instructions" in called_with


async def test_run_with_empty_messages():
    """run() handles empty messages list gracefully."""
    stub = StubNode("response")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "No input needed", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    result = await loop.run(agent, messages=[], tools=[], stream=False)
    assert isinstance(result, str)
    # No user messages to record, but assistant response is still recorded
    assistant_msgs = [m for m in loop.root_session.chat_history if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1]["content"] == "No input needed"


async def test_run_stream_records_chat_history():
    """run(stream=True) records accumulated content in chat_history."""
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []

    async def mock_stream(*args, **kwargs):
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream
    messages = [{"role": "user", "content": "hi"}]
    result = await loop.run(agent, messages, tools=[], stream=True)
    events = [e async for e in result]
    assert len(events) == 3
    assistant_msgs = [m for m in loop.root_session.chat_history if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1]["content"] == "Hello world"


async def test_ensure_terminal_skipped_when_no_default():
    """run() skips ensure_terminal() when default_terminal_node is None."""
    stub = StubNode("response")
    terminal = StubResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue, default_terminal_node=None)
    original = loop.queue.ensure_terminal
    called = False

    def track_call(*args, **kwargs):
        nonlocal called
        called = True
        return original(*args, **kwargs)

    loop.queue.ensure_terminal = track_call

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None})

    await loop.run(agent, [{"role": "user", "content": "hi"}], tools=[], stream=False)
    assert not called, "ensure_terminal should not be called when default_terminal_node is None"


async def test_tinycua_loop_ensure_terminal_bootstrap():
    """run() calls ensure_terminal() on queue at bootstrap."""
    terminal_node = StubResponseNode()

    loop = TinyCUALoop(default_terminal_node=terminal_node)
    queue = loop.queue

    original_ensure_terminal = queue.ensure_terminal
    ensure_terminal_called = []

    def mock_ensure_terminal(default_terminal_node):
        ensure_terminal_called.append(default_terminal_node)
        return original_ensure_terminal(default_terminal_node)

    queue.ensure_terminal = mock_ensure_terminal

    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "test"}]

    await loop.run(agent, messages, tools=[], stream=False)

    assert len(ensure_terminal_called) == 1
    assert ensure_terminal_called[0] is terminal_node


# --- Mandatory Passthrough Unit Tests ---


def test_on_reviewer_open_question_installs_passthrough():
    """_on_reviewer_open_question installs MandatoryPassthrough targeting ResultReviewer."""
    # Arrange
    loop = TinyCUALoop()
    session = Session()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer.ensure_session(session)
    loop.queue.items = [loop.queue.items[0], reviewer, loop.queue.items[-1]]
    active_task = Task(task_id="task_1", title="test task", description="test task")

    # Act
    loop._on_reviewer_open_question(active_task)

    # Assert
    assert loop._pending_mandatory_passthrough is not None
    assert loop._pending_mandatory_passthrough.target_node_id == "reviewer_1"
    assert loop._pending_mandatory_passthrough.target_session_id == session.session_id
    assert loop._pending_mandatory_passthrough.allow_query_analyst_restart is True


def test_on_reviewer_open_question_preserves_active_task():
    """_on_reviewer_open_question does not modify the active task status during installation."""
    # Arrange
    loop = TinyCUALoop()
    session = Session()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer.ensure_session(session)
    loop.queue.items = [loop.queue.items[0], reviewer, loop.queue.items[-1]]
    active_task = Task(task_id="task_1", title="test task", description="test task", status="in_progress")

    # Act
    loop._on_reviewer_open_question(active_task)

    # Assert — task is unchanged (status preserved, not marked done or removed)
    assert active_task.task_id == "task_1"
    assert active_task.status == "in_progress"  # status was preserved
    assert loop._pending_mandatory_passthrough is not None  # passthrough was installed


def test_on_reviewer_open_question_no_reviewer_logs_warning():
    """_on_reviewer_open_question warns when no ResultReviewer found in queue."""
    # Arrange
    loop = TinyCUALoop()
    active_task = Task(task_id="task_1", title="test task", description="test task")

    # Act
    loop._on_reviewer_open_question(active_task)

    # Assert
    assert loop._pending_mandatory_passthrough is None


def test_install_mandatory_passthrough_clears_previous():
    """_install_mandatory_passthrough replaces any existing passthrough."""
    # Arrange
    loop = TinyCUALoop()
    first = MandatoryPassthrough(target_node_id="first", reason="first")
    second = MandatoryPassthrough(target_node_id="second", reason="second")

    # Act
    loop._install_mandatory_passthrough(first)
    loop._install_mandatory_passthrough(second)

    # Assert
    assert loop._pending_mandatory_passthrough.target_node_id == "second"


def test_clear_mandatory_passthrough():
    """_clear_mandatory_passthrough removes the pending directive."""
    # Arrange
    loop = TinyCUALoop()
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="test", reason="test"
    )

    # Act
    loop._clear_mandatory_passthrough()

    # Assert
    assert loop._pending_mandatory_passthrough is None


def test_stale_passthrough_restart_false_drops_continuation():
    """Stale passthrough with allow_query_analyst_restart=False is dropped silently."""
    # Arrange
    loop = TinyCUALoop()
    session = Session()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer.ensure_session(session)
    loop.queue.items = [loop.queue.items[0], reviewer, loop.queue.items[-1]]

    # Install a passthrough with allow_query_analyst_restart=False
    stale_session = Session()  # different session = stale
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="reviewer_1",
        target_session_id=stale_session.session_id,
        allow_query_analyst_restart=False,
    )

    # Act — simulate precheck with stale session
    from tinycua.models.node_input import NodeInput

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "user continuation"}],
        metadata={"mandatory_passthrough": loop._pending_mandatory_passthrough},
    )
    from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
    qa = TinyCUAQueryAnalystNode()
    qa.ensure_session(session)
    result = qa.check_mandatory_passthrough(
        input_data=input_data,
    )

    # Assert — passthrough is dropped, no restart
    assert result is None


def test_no_active_task_does_not_install_passthrough():
    """_on_reviewer_open_question(None) does not install passthrough when no active task."""
    # Arrange
    loop = TinyCUALoop()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer.ensure_session(loop.root_session)
    loop.queue.items = [loop.queue.items[0], reviewer, loop.queue.items[-1]]

    # Act
    loop._on_reviewer_open_question(None)

    # Assert — no passthrough installed
    assert loop._pending_mandatory_passthrough is None


def test_find_result_reviewer_returns_first_match():
    """_find_result_reviewer returns the first ResultReviewer in queue."""
    # Arrange
    loop = TinyCUALoop()
    reviewer_a = TinyCUAResultReviewerNode(
        node_id="reviewer_a",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer_b = TinyCUAResultReviewerNode(
        node_id="reviewer_b",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    loop.queue.items = [loop.queue.items[0], reviewer_a, reviewer_b, loop.queue.items[-1]]

    # Act
    result = loop._find_result_reviewer()

    # Assert — first match is returned
    assert result is not None
    assert result.node_id == "reviewer_a"


def test_build_query_analyst_input_injects_pending_passthrough():
    """_build_query_analyst_input can carry passthrough when injected."""
    # Arrange
    loop = TinyCUALoop()
    session = Session()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer.ensure_session(session)
    loop.queue.items = [loop.queue.items[0], reviewer, loop.queue.items[-1]]

    # Install a pending passthrough
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="reviewer_1",
        target_session_id=session.session_id,
        reason="test injection",
    )

    # Act — simulate _execute_decision_node building QueryAnalyst input
    input_data = loop._build_query_analyst_input()
    if loop._pending_mandatory_passthrough is not None:
        input_data.metadata["mandatory_passthrough"] = loop._pending_mandatory_passthrough

    # Assert — passthrough is injected into metadata
    assert "mandatory_passthrough" in input_data.metadata
    assert input_data.metadata["mandatory_passthrough"].target_node_id == "reviewer_1"
    assert input_data.metadata["mandatory_passthrough"].target_session_id == session.session_id


def test_ensure_query_analyst_at_front_moves_existing_qa():
    """_ensure_query_analyst_at_front moves QueryAnalyst to front when it exists elsewhere."""
    # Arrange
    loop = TinyCUALoop()
    from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode

    qa = TinyCUAQueryAnalystNode()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    terminal = loop.queue.items[-1]
    # Queue: [reviewer, qa, terminal] — QA is NOT at front
    loop.queue.items = [reviewer, qa, terminal]

    # Act
    loop._ensure_query_analyst_at_front()

    # Assert — QA is now at front
    assert isinstance(loop.queue.items[0], TinyCUAQueryAnalystNode)
    assert loop.queue.items[0] is qa


def test_ensure_query_analyst_at_front_already_at_front():
    """_ensure_query_analyst_at_front is no-op when QA is already at front."""
    # Arrange
    loop = TinyCUALoop()
    original_items = list(loop.queue.items)

    # Act
    loop._ensure_query_analyst_at_front()

    # Assert — unchanged
    assert loop.queue.items[0] is original_items[0]
    assert len(loop.queue.items) == len(original_items)


def test_ensure_query_analyst_at_front_creates_fresh():
    """_ensure_query_analyst_at_front creates fresh QA when none found in queue."""
    # Arrange
    loop = TinyCUALoop()
    from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode

    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    terminal = loop.queue.items[-1]
    # Queue with no QA
    loop.queue.items = [reviewer, terminal]

    # Act
    loop._ensure_query_analyst_at_front()

    # Assert — fresh QA was created and placed at front
    assert isinstance(loop.queue.items[0], TinyCUAQueryAnalystNode)
    # The new QA should be a different instance
    assert loop.queue.items[0].node_id == "query_analyst"
