"""Integration tests for node transport via NodeInput/NodePayload."""

from __future__ import annotations

from typing import Literal


def test_node_payload_round_trip_through_node_handoff() -> None:
    """NodePayload carries structured output through serialize -> deserialize -> convert."""
    from tinycua.models import NodeInput, NodePayload, convert_node_input_to_messages

    # Arrange: Node A produces a task analysis payload
    payload = NodePayload(
        payload_type="task_analysis",
        source_node="TaskAnalyzer",
        content={"task_id": "T-0.1", "status": "analyzed"},
        metadata={"confidence": 0.95},
    )
    node_input = NodeInput(
        input_type="continuation",
        source_node="TaskAnalyzer",
        target_node="TaskExecutor",
        payloads=[payload],
        messages=[{"role": "user", "content": "Analyze task T-0.1"}],
    )

    # Act: serialize -> deserialize -> convert to messages
    json_str = node_input.to_json()
    restored = NodeInput.from_json(json_str)
    messages = convert_node_input_to_messages(restored)

    # Assert: messages contain payload as assistant message + continuation user message
    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert "T-0.1" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Analyze task T-0.1"


def test_node_input_like_union_type_in_build_messages() -> None:
    """NodeInputLike union type works in a mock node build_messages() method."""
    from tinycua.models import (
        NodeInput,
        NodeInputLike,
        NodePayload,
        convert_node_input_to_messages,
    )

    def build_messages(
        node_input: NodeInputLike,
        *,
        source: Literal["external", "internal"] = "internal",
    ) -> list[dict]:
        return convert_node_input_to_messages(node_input, source=source)

    # External user string
    user_msgs = build_messages("What is the weather?", source="external")
    assert user_msgs == [{"role": "user", "content": "What is the weather?"}]

    # Internal strings use user role to avoid provider assistant-prefill behavior.
    assistant_msgs = build_messages("I will analyze the task.")
    assert assistant_msgs == [
        {"role": "user", "content": "I will analyze the task."}
    ]

    # NodePayload
    payload = NodePayload(payload_type="decision", content="approved")
    payload_msgs = build_messages(payload)
    assert payload_msgs[0]["role"] == "assistant"

    # NodeInput
    node_input = NodeInput(input_type="initial", payloads=[payload])
    node_msgs = build_messages(node_input)
    assert len(node_msgs) == 1

    # list[dict] passthrough
    prebuilt = [{"role": "user", "content": "hello"}]
    passthrough_msgs = build_messages(prebuilt)
    assert passthrough_msgs is prebuilt


def test_node_input_messages_compatible_with_session_context() -> None:
    """NodeInput.to_messages() output matches Session.session_context format."""
    from tinycua.models import NodeInput, NodePayload
    from tinycua.models.session import Session

    payload = NodePayload(payload_type="task_analysis", content={"task_id": "T-0.1"})
    node_input = NodeInput(input_type="continuation", payloads=[payload])
    messages = node_input.to_messages()

    # Verify format matches what Session expects
    session = Session(session_context=messages)
    assert session.session_context == messages
    assert all(isinstance(m, dict) for m in session.session_context)
    assert all("role" in m and "content" in m for m in session.session_context)
