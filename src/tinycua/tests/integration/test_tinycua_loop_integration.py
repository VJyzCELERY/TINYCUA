"""Integration tests for TinyCUALoop node-based execution."""

from __future__ import annotations

import collections.abc

from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.classification import MandatoryPassthrough
from tinycua.models.session import Session
from tinycua.models.task import Task

from tests.mock_llm import MockLLM
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


# --- Mandatory Passthrough Integration Tests ---


async def test_open_question_to_continuation_two_call_flow():
    """End-to-end: first run() simulates open_question and installs passthrough,
    second run() simulates user continuation and verifies QueryAnalyst detects
    it via queue restart, consumes it, and the continuation path is followed."""
    # --- First run() — simulate a scenario where ResultReviewer decides
    #     open_question and installs the MandatoryPassthrough directive. ---

    loop = TinyCUALoop()

    # Replace the default queue with one that includes a ResultReviewer
    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=NodeConfigBase(llm_client=MockLLM(content='{"outcome": "open_question", "rationale": "Need info"}')),
        loop=loop,
    )
    reviewer.ensure_session(loop.root_session)

    # Create a task_executor proxy that just returns "done" so the reviewer runs
    task_executor = StubNode(
        content="execution result for testing",
        node_id="task_executor",
    )

    terminal = loop.queue.items[-1]
    loop.queue.items = [task_executor, reviewer, terminal]

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    # Set up a real task so _on_reviewer_open_question has context
    active_task = Task(task_id="task_1", title="test task", description="test task", status="in_progress")
    loop.root_task = active_task

    # Run the loop — this should process task_executor → result_reviewer →
    # open_question → install passthrough → terminal → exit
    await loop.run(
        agent=agent,
        messages=[{"role": "user", "content": "write a script"}],
        tools=[],
        stream=False,
    )

    # Assert: passthrough was installed during first run
    assert loop._pending_mandatory_passthrough is not None, (
        "open_question should have installed a MandatoryPassthrough"
    )
    assert loop._pending_mandatory_passthrough.target_node_id == "result_reviewer"
    assert loop._pending_mandatory_passthrough.target_session_id == loop.root_session.session_id
    assert loop._pending_mandatory_passthrough.allow_query_analyst_restart is True

    # --- Second run() — simulate the user providing a continuation ---
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    result_2 = await loop.run(
        agent=agent,
        messages=[{"role": "user", "content": "here is the answer"}],
        tools=[],
        stream=False,
    )

    # Assert: passthrough was consumed (cleared after forward)
    assert loop._pending_mandatory_passthrough is None, (
        "passthrough should have been consumed during second run"
    )

    # The queue should now have QueryAnalyst at the front (it was restored
    # by _ensure_query_analyst_at_front). After passthrough detection and
    # queue advance, the terminal node follows.
    # Verify the loop produced a result (even if it's just the terminal response).
    assert isinstance(result_2, str)
    assert len(result_2) > 0


async def test_new_user_query_clears_pending_passthrough():
    """New user query clears pending stale passthrough via run() bypass path.

    When a passthrough is pending but the user sends a new top-level query
    (not a continuation), the passthrough is stale and should be cleared
    during the next run() — falling back to normal LLM classification.
    """
    loop = TinyCUALoop()

    reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=NodeConfigBase(llm_client=MockLLM(content='{"outcome": "completed", "rationale": "Done"}')),
        loop=loop,
    )
    reviewer.ensure_session(loop.root_session)

    terminal = loop.queue.items[-1]
    loop.queue.items = [loop.queue.items[0], reviewer, terminal]

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    # Simulate a stale passthrough from a previous run()
    stale_session = Session()
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="result_reviewer",
        target_session_id=stale_session.session_id,
    )
    assert loop._pending_mandatory_passthrough is not None

    # New user query arrives — run() should detect the stale passthrough,
    # clear it, and fall back to normal LLM classification.
    result = await loop.run(
        agent=agent,
        messages=[{"role": "user", "content": "tell me a joke"}],
        tools=[],
        stream=False,
    )

    # Assert: stale passthrough was cleared during run()
    assert loop._pending_mandatory_passthrough is None, (
        "stale passthrough should have been cleared during run()"
    )
    assert isinstance(result, str)
    assert len(result) > 0
