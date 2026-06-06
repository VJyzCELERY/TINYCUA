"""Unit tests for NodePayload dataclass."""

from __future__ import annotations

from dataclasses import dataclass

from tinycua.models import NodePayload, StateObject


def test_construction_with_all_fields() -> None:
    """NodePayload can be constructed with all fields specified."""
    payload = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1"},
        metadata={"confidence": 0.95},
    )

    assert payload.payload_type == "task_analysis"
    assert payload.source_node == "TaskAnalyzer"
    assert payload.content == {"task_id": "T-0.1"}
    assert payload.metadata == {"confidence": 0.95}


def test_construction_with_defaults() -> None:
    """NodePayload defaults source_node to None and metadata to {}."""
    payload = NodePayload(payload_type="decision")

    assert payload.payload_type == "decision"
    assert payload.source_node is None
    assert payload.metadata == {}


def test_to_message_with_string_content() -> None:
    """to_message() with string content produces assistant-role message."""
    payload = NodePayload(payload_type="status", content="completed")
    message = payload.to_message()

    assert message["role"] == "assistant"
    assert message["content"] == "completed"


def test_to_message_with_dict_content() -> None:
    """to_message() with dict content serializes via json.dumps()."""
    payload = NodePayload(
        payload_type="task_analysis",
        content={"task_id": "T-0.1", "status": "analyzed"},
    )
    message = payload.to_message()

    assert message["role"] == "assistant"
    # Dict content should be serialized as JSON string
    assert isinstance(message["content"], str)
    assert "task_id" in message["content"]
    assert "T-0.1" in message["content"]


def test_to_message_with_state_object_content() -> None:
    """to_message() with StateObject content serializes via .to_json()."""

    @dataclass
    class AnalysisResult(StateObject):
        task_id: str = ""
        confidence: float = 0.0

    content = AnalysisResult(task_id="T-0.1", confidence=0.95)
    payload = NodePayload(payload_type="analysis", content=content)
    message = payload.to_message()

    assert message["role"] == "assistant"
    # StateObject content should be serialized as JSON string
    assert isinstance(message["content"], str)
    assert "T-0.1" in message["content"]


def test_to_message_with_list_of_dicts_content() -> None:
    """to_message() with list[dict] content serializes via json.dumps()."""
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    payload = NodePayload(payload_type="conversation", content=messages)
    message = payload.to_message()

    assert message["role"] == "assistant"
    # List content should be serialized as JSON string
    assert isinstance(message["content"], str)
    assert "hello" in message["content"]


def test_to_message_with_none_content() -> None:
    """to_message() with None content produces empty string for LLM compatibility."""
    payload = NodePayload(payload_type="empty", content=None)
    message = payload.to_message()

    assert message["role"] == "assistant"
    assert message["content"] == ""


def test_to_messages_returns_single_element_list() -> None:
    """to_messages() returns single-element list from to_message()."""
    payload = NodePayload(payload_type="decision", content="approved")
    messages = payload.to_messages()

    assert len(messages) == 1
    assert messages[0] == payload.to_message()


def test_round_trip_dict() -> None:
    """NodePayload survives to_dict() -> from_dict() round-trip."""
    original = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1"},
        metadata={"confidence": 0.95},
    )
    restored = NodePayload.from_dict(original.to_dict())

    assert restored.payload_type == original.payload_type
    assert restored.source_node == original.source_node
    assert restored.content == original.content
    assert restored.metadata == original.metadata


def test_round_trip_json() -> None:
    """NodePayload survives to_json() -> from_json() round-trip."""
    original = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1"},
        metadata={"confidence": 0.95},
    )
    restored = NodePayload.from_json(original.to_json())

    assert restored.payload_type == original.payload_type
    assert restored.source_node == original.source_node
    assert restored.content == original.content
    assert restored.metadata == original.metadata
