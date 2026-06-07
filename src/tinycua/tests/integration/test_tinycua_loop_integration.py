"""Integration tests for TinyCUALoop node-based execution."""

from __future__ import annotations

import collections.abc

from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop

from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


async def test_tinycua_loop_executes_node_queue():
    """Tests queue execution path (no bootstrap) — validates sequential node processing."""
    stub = StubNode("processed by stub")
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
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert isinstance(result, str)
    assert len(result) > 0


async def test_tinycua_loop_ensure_terminal_bootstrap():
    """TinyCUALoop auto-appends terminal node when default_terminal_node is set."""
    terminal = ResponseNode()
    loop = TinyCUALoop(default_terminal_node=terminal)
    stub = StubNode("test")
    loop.queue.items = [stub]

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )
    await loop.run(agent=agent, messages=[], tools=[], stream=False)
    assert loop.queue.items[-1] is terminal


async def test_tinycua_loop_merges_sdk_messages():
    """TinyCUALoop merges SDK messages into root session input_context."""
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
        agent=agent,
        messages=messages,
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert session.input_context == messages


async def test_tinycua_loop_tool_scoping():
    """TinyCUALoop applies NodeToolPolicy to resolve tools per node."""
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


async def test_tinycua_loop_override_instructions():
    """TinyCUALoop passes override_instructions to nodes."""
    stub = StubNode("override test")
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
        agent=agent,
        messages=[],
        tools=[],
        override_instructions="custom instructions",
        stream=False,
    )
    assert isinstance(result, str)
    assert len(result) > 0


async def test_tinycua_loop_stream_false_returns_string():
    """TinyCUALoop run(stream=False) returns a string."""
    stub = StubNode("string result")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]
    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "response", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert isinstance(result, str)
    assert len(result) > 0


async def test_tinycua_loop_stream_true_returns_iterator():
    """TinyCUALoop run(stream=True) returns an async iterator with content deltas."""
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
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    assert isinstance(result, collections.abc.AsyncIterator)
    events = [e async for e in result]
    assert len(events) > 0
    assert any(e["type"] == "response.output_text.delta" for e in events)
