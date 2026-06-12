"""Tests for TinyCUALoop — node execution, message merging, tool scoping, override, streaming."""

from __future__ import annotations

import collections.abc

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua_sdk.agent import BaseLoop

from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


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
    """TinyCUALoop creates a NodeQueue by default."""
    loop = TinyCUALoop()
    assert isinstance(loop.queue, NodeQueue)
    assert loop.queue.is_empty() is True


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
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    loop = TinyCUALoop()
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
    loop = TinyCUALoop()
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
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    # chat_history should not contain user messages (ChatRecord objects)
    chat_user_msgs = [m for m in loop.root_session.chat_history if m.role == "user"]
    assert len(chat_user_msgs) == 0


async def test_run_records_assistant_response():
    """run() records assistant response in chat_history."""
    stub = StubNode("response")
    terminal = ResponseNode()
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
    assistant_msgs = [m for m in loop.root_session.chat_history if m.role == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1].content == "Hello there"


async def test_run_calls_build_system_message_with_override():
    """run() passes override_instructions to node execution via _build_node_messages."""
    stub = StubNode("response")
    terminal = ResponseNode()
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
    terminal = ResponseNode()
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
    assistant_msgs = [m for m in loop.root_session.chat_history if m.role == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1].content == "No input needed"


async def test_run_stream_records_chat_history():
    """run(stream=True) records accumulated content in chat_history."""
    terminal = ResponseNode()
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
    assistant_msgs = [m for m in loop.root_session.chat_history if m.role == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[-1].content == "Hello world"


async def test_ensure_terminal_skipped_when_no_default():
    """run() skips ensure_terminal() when default_terminal_node is None."""
    stub = StubNode("response")
    terminal = ResponseNode()
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
    terminal_node = ResponseNode()

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
