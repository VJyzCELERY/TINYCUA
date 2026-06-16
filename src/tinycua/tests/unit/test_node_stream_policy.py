"""Unit tests for NodeStreamPolicy enforcement in TinyCUALoop._run_stream().

Tests that NodeStreamPolicy fields (final_response_only, emit_internal_events,
include_node_metadata) correctly control lifecycle event emission and metadata
enrichment in the streaming code path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeStreamPolicy
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop

from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


def _make_mock_agent(stream_events: list[dict] | None = None) -> MagicMock:
    """Create a MagicMock agent with an async streaming _call_llm."""
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    if stream_events is None:
        stream_events = [
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.completed", "finish_reason": "completed"},
        ]

    async def _call_llm(*args, **kwargs):  # noqa: ARG001
        for event in stream_events:
            yield event

    agent._call_llm = _call_llm
    return agent


async def test_emit_internal_events_true_emits_lifecycle():
    """With emit_internal_events=True (default), lifecycle events are emitted."""
    stub = StubNode("lifecycle test")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    events = [e async for e in result]
    lifecycle_types = [e["type"] for e in events if e["type"].startswith("node.")]
    assert "node.started" in lifecycle_types
    assert "node.llm_call" in lifecycle_types
    assert "node.completed" in lifecycle_types


async def test_emit_internal_events_false_suppresses_lifecycle():
    """With emit_internal_events=False, no node.* lifecycle events are emitted."""
    policy = NodeStreamPolicy(emit_internal_events=False)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("suppression test")
    stub.config = config
    terminal = ResponseNode()
    terminal.config = config
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    events = [e async for e in result]
    lifecycle_events = [e for e in events if e["type"].startswith("node.")]
    assert len(lifecycle_events) == 0


async def test_include_node_metadata_true_enriches_events():
    """With include_node_metadata=True, events include node_id and node_type."""
    policy = NodeStreamPolicy(include_node_metadata=True)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("meta test")
    stub.config = config
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    events = [e async for e in result]
    metadata_events = [e for e in events if e.get("node_id") is not None]
    assert len(metadata_events) > 0
    for e in metadata_events:
        assert "node_id" in e
        assert "node_type" in e


async def test_include_node_metadata_false_no_enrichment():
    """With include_node_metadata=False, LLM events have no node_id/node_type."""
    policy = NodeStreamPolicy(include_node_metadata=False)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("no meta test")
    stub.config = config
    terminal = ResponseNode()
    terminal.config = config  # Apply same policy to terminal
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    events = [e async for e in result]
    # LLM events (non-lifecycle) should not have node metadata when disabled
    llm_events = [
        e
        for e in events
        if not e["type"].startswith("node.")
        and not e["type"].startswith("transcript.")
    ]
    for e in llm_events:
        assert "node_id" not in e
        assert "node_type" not in e


async def test_final_response_only_suppresses_intermediate_events():
    """With final_response_only=True, only terminal node events are emitted."""
    policy = NodeStreamPolicy(final_response_only=True)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("intermediate")
    stub.config = config
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    events = [e async for e in result]
    node_ids = {e.get("node_id") for e in events if e.get("node_id")}
    assert "stub" not in node_ids
    # Terminal node events should still appear
    assert "response" in node_ids


async def test_final_response_only_false_emits_all_events():
    """With final_response_only=False (default), all node events are emitted."""
    policy = NodeStreamPolicy(final_response_only=False)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("all events")
    stub.config = config
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    events = [e async for e in result]
    node_ids = {e.get("node_id") for e in events if e.get("node_id")}
    assert "stub" in node_ids
    assert "response" in node_ids
