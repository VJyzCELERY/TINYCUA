"""Unit tests for stream event models and helpers.

Tests StreamEvent dict shape, LifecycleEvent creation via factory,
enrich_stream_event metadata injection, and TranscriptRecord serialization.
"""

from __future__ import annotations

import json

from tinycua.config.types import TranscriptRecord
from tinycua.models.stream_event import enrich_stream_event, make_lifecycle_event


def test_make_lifecycle_event_started():
    """Test make_lifecycle_event creates a valid node.started event."""
    event = make_lifecycle_event(
        event_type="node.started",
        node_id="worker-1",
        node_type="ProcessNode",
        attempt=1,
    )
    assert event["type"] == "node.started"
    assert event["node_id"] == "worker-1"
    assert event["node_type"] == "ProcessNode"
    assert event["attempt"] == 1
    assert event["content"] is None
    assert event["finish_reason"] is None
    assert event["metadata"] == {}
    assert isinstance(event["timestamp"], float)


def test_make_lifecycle_event_completed():
    """Test make_lifecycle_event creates a valid node.completed event."""
    event = make_lifecycle_event(
        event_type="node.completed",
        node_id="worker-2",
        node_type="DecisionNode",
        attempt=2,
        content="final answer",
        finish_reason="completed",
        metadata={"route_label": "analysis"},
    )
    assert event["type"] == "node.completed"
    assert event["content"] == "final answer"
    assert event["finish_reason"] == "completed"
    assert event["attempt"] == 2
    assert event["metadata"]["route_label"] == "analysis"


def test_make_lifecycle_event_error():
    """Test make_lifecycle_event creates a valid node.error event."""
    event = make_lifecycle_event(
        event_type="node.error",
        node_id="worker-3",
        node_type="ProcessNode",
        attempt=3,
        finish_reason="error",
    )
    assert event["type"] == "node.error"
    assert event["finish_reason"] == "error"


def test_enrich_stream_event_with_metadata():
    """Test enrich_stream_event adds node metadata when enabled."""
    event = {"type": "response.output_text.delta", "delta": "Hello"}
    enriched = enrich_stream_event(
        event,
        node_id="node-1",
        node_type="ProcessNode",
        attempt=2,
        include_metadata=True,
    )
    assert enriched is event  # mutates in place
    assert enriched["node_id"] == "node-1"
    assert enriched["node_type"] == "ProcessNode"
    assert enriched["attempt"] == 2
    assert enriched["delta"] == "Hello"  # original field preserved


def test_enrich_stream_event_without_metadata():
    """Test enrich_stream_event skips metadata when disabled."""
    event = {"type": "response.output_text.delta", "delta": "Hello"}
    enriched = enrich_stream_event(
        event,
        node_id="node-1",
        node_type="ProcessNode",
        include_metadata=False,
    )
    assert enriched is event
    assert "node_id" not in enriched
    assert "node_type" not in enriched


def test_transcript_record_to_dict():
    """Test TranscriptRecord serialization to dict."""
    event = make_lifecycle_event(
        event_type="node.started",
        node_id="w-1",
        node_type="ProcessNode",
    )
    record = TranscriptRecord(
        event=event,
        run_id="run-abc",
        session_id="sess-xyz",
        sequence=0,
    )
    d = record.to_dict()
    assert d["run_id"] == "run-abc"
    assert d["session_id"] == "sess-xyz"
    assert d["sequence"] == 0
    assert d["event"]["type"] == "node.started"
    assert d["event"]["node_id"] == "w-1"


def test_transcript_record_jsonl_roundtrip():
    """Test TranscriptRecord survives JSONL serialize/deserialize."""
    event = make_lifecycle_event(
        event_type="node.completed",
        node_id="w-2",
        node_type="DecisionNode",
        content="result",
        finish_reason="completed",
    )
    record = TranscriptRecord(
        event=event,
        run_id="run-123",
        session_id="sess-456",
        sequence=7,
    )
    jsonl_line = json.dumps(record.to_dict())
    parsed = json.loads(jsonl_line)
    assert parsed["event"] == event
    assert parsed["run_id"] == "run-123"
    assert parsed["sequence"] == 7
