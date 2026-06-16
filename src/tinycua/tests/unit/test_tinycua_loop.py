"""Tests for TinyCUALoop — node execution, message merging, tool scoping, override, streaming."""

from __future__ import annotations

import collections.abc

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy, create_node_config
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
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


def test_tinycua_loop_has_no_iteration_limit():
    """TinyCUALoop does not impose an iteration limit."""
    loop = TinyCUALoop()
    assert not hasattr(loop, "max_iterations")


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
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    agent._call_llm.assert_called()


async def test_run_sync_continues_until_terminal():
    """Loop continues through nonterminal nodes until ResponseNode."""
    stub = StubNode("node output")
    terminal = ResponseNode()
    queue = NodeQueue(items=[stub, terminal])

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )

    assert agent._call_llm.call_count == 2


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
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
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
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
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
    agent._call_llm = AsyncMock(return_value={"content": "final", "tool_calls": None})

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
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
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

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


async def test_message_merging_preserves_order():
    """Merged messages retain their original order."""
    loop = TinyCUALoop()
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]

    await loop.run(
        agent=agent,
        messages=messages,
        tools=[],
        override_instructions=None,
        stream=False,
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
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions="custom instructions",
        stream=False,
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
    agent._call_llm = AsyncMock(return_value={"content": "ok", "tool_calls": None})

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
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


async def test_run_sync_consumes_canonical_stream_runtime():
    """Non-stream run drains _run_stream instead of executing a second loop."""
    loop = TinyCUALoop()
    calls = 0

    async def fake_stream(agent, tools, override_instructions=None):
        nonlocal calls
        del agent, tools, override_instructions
        calls += 1
        yield {
            "type": "response.output_text.delta",
            "node_id": "response",
            "delta": "final",
        }

    loop._run_stream = fake_stream  # type: ignore[method-assign]

    result = await loop._run_sync(MagicMock(), [], None)

    assert result == "final"
    assert calls == 1


async def test_stream_true_emits_nonterminal_token_deltas():
    """Streaming mode emits token deltas for nonterminal LLM nodes too."""
    stub = StubNode("streaming nonterminal", node_id="planner")
    terminal = ResponseNode()
    queue = NodeQueue(items=[stub, terminal])

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    call_count = 0

    async def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {"type": "response.output_text.delta", "delta": "plan"}
            yield {"type": "response.output_text.delta", "delta": " tokens"}
        else:
            yield {"type": "response.output_text.delta", "delta": " final"}

    agent._call_llm = mock_stream

    result = await loop.run(agent, messages=[], tools=[], stream=True)
    events = [event async for event in result]

    planner_deltas = [
        event
        for event in events
        if event.get("type") == "response.output_text.delta"
        and event.get("node_id") == "planner"
    ]
    assert [event["delta"] for event in planner_deltas] == ["plan", " tokens"]


async def test_stream_task_executor_receives_injected_active_task_context():
    """Streaming executor path injects the same active-task context as sync path."""
    executor = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    queue = NodeQueue(items=[executor])
    loop = TinyCUALoop(queue=queue)
    root = loop.root_session.task_store.create_task("Build application")
    active = loop.root_session.task_store.create_task(
        "Create requirements.txt",
        parent_id=root.task_id,
    )
    loop.root_session.task_store.active_task_id = active.task_id
    captured_messages = []

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    async def mock_stream(messages, tools, *, stream=False):
        del tools, stream
        captured_messages.extend(messages)
        yield {"type": "response.output_text.delta", "delta": "working"}

    agent._call_llm = mock_stream

    async for _event in loop._stream_node_events(
        executor,
        agent,
        [],
        None,
        loop.queue.input_for_current(),
    ):
        pass

    rendered = "\n".join(str(message.get("content", "")) for message in captured_messages)
    assert "Create requirements.txt" in rendered
    assert "Build application" in rendered


async def test_stream_digester_digest_only_does_not_route_to_response():
    """Digester may choose digest-only without terminal failure routing."""
    digester = TinyCUAInformationDigesterNode(
        node_id="digester",
        config=create_node_config("digester"),
    )
    response = ResponseNode()
    queue = NodeQueue(items=[digester, response])
    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    async def mock_stream(messages, tools, *, stream=False):
        del messages, tools, stream
        return {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_digest",
                    "type": "function",
                    "function": {
                        "name": "digest_information",
                        "arguments": '{"information":"notes app"}',
                    },
                },
            ],
        }

    agent._call_llm = mock_stream

    events = [
        event
        async for event in loop._stream_node_events(
            digester,
            agent,
            [],
            None,
            loop.queue.input_for_current(),
        )
    ]

    assert any(
        event.get("type") == "node.completed" and event.get("node_id") == "digester"
        for event in events
    )
    assert loop.queue.current is digester
    assert not any(
        entry.get("node_id") == "response" for entry in loop.get_execution_trace()
    )


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
        return_value={
            "content": "Hi",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
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
        return_value={
            "content": "Hello there",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "hi"}]
    await loop.run(agent, messages, tools=[], stream=False)
    assistant_msgs = [
        m for m in loop.root_session.chat_history if m.role == "assistant"
    ]
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
        return_value={
            "content": "ok",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "test"}]
    with pytest.MonkeyPatch.context() as m:
        original_build = loop._build_node_messages
        called_with = []

        def spy_build(node, override=None):
            called_with.append(override)
            return original_build(node, override)

        m.setattr(loop, "_build_node_messages", spy_build)
        await loop.run(
            agent,
            messages,
            tools=[],
            override_instructions="custom instructions",
            stream=False,
        )
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
        return_value={
            "content": "No input needed",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    result = await loop.run(agent, messages=[], tools=[], stream=False)
    assert isinstance(result, str)
    # No user messages to record, but assistant response is still recorded
    assistant_msgs = [
        m for m in loop.root_session.chat_history if m.role == "assistant"
    ]
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
    # Events now include lifecycle events (node.started, node.llm_call, node.completed)
    # in addition to LLM delta events
    delta_events = [e for e in events if e.get("type") == "response.output_text.delta"]
    assert len(delta_events) == 2  # original delta events still present
    assistant_msgs = [
        m for m in loop.root_session.chat_history if m.role == "assistant"
    ]
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
    agent._call_llm = AsyncMock(
        return_value={
            "content": "ok",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )

    await loop.run(agent, [{"role": "user", "content": "hi"}], tools=[], stream=False)
    assert not called, (
        "ensure_terminal should not be called when default_terminal_node is None"
    )


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
        return_value={
            "content": "ok",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "completed",
            "model": None,
        }
    )
    messages = [{"role": "user", "content": "test"}]

    await loop.run(agent, messages, tools=[], stream=False)

    assert len(ensure_terminal_called) == 1
    assert ensure_terminal_called[0] is terminal_node
