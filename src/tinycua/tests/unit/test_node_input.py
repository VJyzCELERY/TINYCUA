"""Unit tests for NodeInput dataclass and convert_node_input_to_messages."""

from __future__ import annotations

from typing import Literal

from tinycua.models import (
    NodeInput,
    NodePayload,
    convert_node_input_to_messages,
)


def test_construction_with_all_fields() -> None:
    """NodeInput can be constructed with all fields specified."""
    payload = NodePayload(payload_type="decision", content="approved")
    node_input = NodeInput(
        input_type="continuation",
        source_node="TaskAnalyzer",
        target_node="TaskExecutor",
        payloads=[payload],
        messages=[{"role": "user", "content": "hello"}],
        metadata={"step": 1},
    )

    assert node_input.input_type == "continuation"
    assert node_input.source_node == "TaskAnalyzer"
    assert node_input.target_node == "TaskExecutor"
    assert len(node_input.payloads) == 1
    assert len(node_input.messages) == 1
    assert node_input.metadata == {"step": 1}


def test_construction_with_defaults() -> None:
    """NodeInput defaults source_node, target_node to None and metadata to {}."""
    node_input = NodeInput(input_type="initial")

    assert node_input.input_type == "initial"
    assert node_input.source_node is None
    assert node_input.target_node is None
    assert node_input.messages == []
    assert node_input.payloads == []
    assert node_input.metadata == {}


def test_to_messages_payloads_only() -> None:
    """to_messages() with payloads only returns converted payloads."""
    payload1 = NodePayload(payload_type="status", content="running")
    payload2 = NodePayload(payload_type="result", content="done")
    node_input = NodeInput(
        input_type="continuation",
        payloads=[payload1, payload2],
    )

    messages = node_input.to_messages()

    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert messages[0]["content"] == "running"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "done"


def test_to_messages_messages_only() -> None:
    """to_messages() with messages only returns the messages list."""
    node_input = NodeInput(
        input_type="continuation",
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    )

    messages = node_input.to_messages()

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_to_messages_both_payloads_and_messages() -> None:
    """to_messages() with both payloads and messages returns payloads first then messages."""
    payload = NodePayload(payload_type="analysis", content="complete")
    node_input = NodeInput(
        input_type="continuation",
        payloads=[payload],
        messages=[{"role": "user", "content": "next step"}],
    )

    messages = node_input.to_messages()

    assert len(messages) == 2
    # Payload first (assistant role)
    assert messages[0]["role"] == "assistant"
    assert messages[0]["content"] == "complete"
    # Then continuation message
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "next step"


def test_to_messages_empty() -> None:
    """to_messages() with empty payloads and messages returns empty list."""
    node_input = NodeInput(input_type="empty")

    messages = node_input.to_messages()

    assert messages == []


def test_round_trip_dict() -> None:
    """NodeInput survives to_dict() -> from_dict() round-trip."""
    payload = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1"},
    )
    original = NodeInput(
        input_type="continuation",
        source_node="TaskAnalyzer",
        target_node="TaskExecutor",
        payloads=[payload],
        messages=[{"role": "user", "content": "hello"}],
        metadata={"step": 1},
    )
    restored = NodeInput.from_dict(original.to_dict())

    assert restored.input_type == original.input_type
    assert restored.source_node == original.source_node
    assert restored.target_node == original.target_node
    assert len(restored.payloads) == 1
    assert restored.payloads[0].payload_type == "task_analysis"
    assert restored.messages == original.messages
    assert restored.metadata == original.metadata


def test_round_trip_json() -> None:
    """NodeInput survives to_json() -> from_json() round-trip."""
    payload = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1"},
    )
    original = NodeInput(
        input_type="continuation",
        source_node="TaskAnalyzer",
        target_node="TaskExecutor",
        payloads=[payload],
        messages=[{"role": "user", "content": "hello"}],
        metadata={"step": 1},
    )
    restored = NodeInput.from_json(original.to_json())

    assert restored.input_type == original.input_type
    assert restored.source_node == original.source_node
    assert restored.target_node == original.target_node
    assert len(restored.payloads) == 1
    assert restored.payloads[0].payload_type == "task_analysis"
    assert restored.messages == original.messages
    assert restored.metadata == original.metadata


def test_convert_external_string() -> None:
    """convert_node_input_to_messages() with external string produces user-role message."""
    result = convert_node_input_to_messages("What is the weather?", source="external")

    assert result == [{"role": "user", "content": "What is the weather?"}]


def test_convert_internal_string() -> None:
    """convert_node_input_to_messages() with internal string produces assistant-role message."""
    result = convert_node_input_to_messages("I will analyze the task.")

    assert result == [{"role": "assistant", "content": "I will analyze the task."}]


def test_convert_node_input() -> None:
    """convert_node_input_to_messages() with NodeInput calls to_messages()."""
    payload = NodePayload(payload_type="decision", content="approved")
    node_input = NodeInput(input_type="initial", payloads=[payload])

    result = convert_node_input_to_messages(node_input)

    assert result == node_input.to_messages()


def test_convert_node_payload() -> None:
    """convert_node_input_to_messages() with NodePayload calls to_messages()."""
    payload = NodePayload(payload_type="decision", content="approved")

    result = convert_node_input_to_messages(payload)

    assert result == payload.to_messages()


def test_convert_list_of_dicts_passthrough() -> None:
    """convert_node_input_to_messages() with list[dict] passes through directly."""
    prebuilt = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]

    result = convert_node_input_to_messages(prebuilt)

    assert result is prebuilt


def test_convert_empty_payloads_returns_empty() -> None:
    """convert_node_input_to_messages() with empty NodeInput returns empty list."""
    node_input = NodeInput(input_type="empty")

    result = convert_node_input_to_messages(node_input)

    assert result == []


def test_convert_default_source_is_internal() -> None:
    """convert_node_input_to_messages() defaults source to 'internal'."""
    result = convert_node_input_to_messages("Hello")

    assert result == [{"role": "assistant", "content": "Hello"}]
