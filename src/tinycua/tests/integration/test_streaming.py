"""Integration tests for streaming and transcript events.

Covers lifecycle event emission, node metadata enrichment,
final_response_only suppression, and JSONL transcript serialization.
See test_tinycua_loop_integration.py for basic stream=False/stream=True
contract tests (scenarios 1 and 2).
"""

from __future__ import annotations

import json

from unittest.mock import MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeStreamPolicy
from tinycua.config.types import TranscriptRecord
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop

from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


def _make_mock_agent(stream_events: list[dict] | None = None) -> MagicMock:
    """Create a MagicMock agent with an async streaming _call_llm.

    Args:
        stream_events: Events to yield. Defaults to a single completed event.
    """
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    if stream_events is None:
        stream_events = [
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.output_text.delta", "delta": " world"},
            {"type": "response.completed", "finish_reason": "completed"},
        ]

    async def _call_llm(*args, **kwargs):  # noqa: ARG001
        for event in stream_events:
            yield event

    agent._call_llm = _call_llm
    return agent


async def test_lifecycle_events_emitted():
    """Verify node lifecycle transitions emit structured events (FR-003)."""
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


async def test_emit_internal_events_suppression():
    """Verify lifecycle events are suppressed when emit_internal_events=False (FR-006)."""
    policy = NodeStreamPolicy(emit_internal_events=False)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("suppression test")
    stub.config = config
    terminal = ResponseNode()
    terminal.config = config  # Apply same suppression policy to terminal
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

    # With emit_internal_events=False, no node.* lifecycle events should appear
    lifecycle_events = [e for e in events if e["type"].startswith("node.")]
    assert len(lifecycle_events) == 0


async def test_node_metadata_in_events():
    """Verify stream events include node_id, node_type, attempt when policy enabled."""
    policy = NodeStreamPolicy(include_node_metadata=True)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("metadata test")
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


async def test_final_response_only_suppresses_intermediate():
    """Verify intermediate node events suppressed when final_response_only=True."""
    policy = NodeStreamPolicy(final_response_only=True)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("intermediate node")
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

    # Only ResponseNode events should be present
    node_ids = {e.get("node_id") for e in events if e.get("node_id")}
    # Intermediate stub node should not appear
    assert "stub" not in node_ids


async def test_transcript_serialization():
    """Verify TranscriptRecord wrapping produces valid JSONL output (FR-007)."""
    stub = StubNode("serialization test")
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

    # Wrap events in TranscriptRecord (validates FR-007)
    records = [
        TranscriptRecord(
            event=e, run_id="test-run", session_id="test-session", sequence=i
        )
        for i, e in enumerate(events)
    ]

    # Serialize to JSONL
    jsonl_lines = [json.dumps(r.to_dict()) for r in records]
    # Parse back
    parsed = [json.loads(line) for line in jsonl_lines]
    assert len(parsed) == len(records)
    for original_record, restored in zip(records, parsed):
        assert restored["run_id"] == "test-run"
        assert restored["session_id"] == "test-session"
        assert restored["event"] == original_record.event
