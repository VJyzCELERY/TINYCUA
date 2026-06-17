"""NodeHandoff transport tests."""

from __future__ import annotations

from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.node_input import convert_node_input_to_messages


def test_node_handoff_renders_as_one_assistant_message() -> None:
    """Generic handoffs are LLM-bound as one assistant message."""
    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Analyze selected unfinished work.",
        payload={"items": [{"id": "task-1", "reason": "too broad"}]},
        constraints=["Do not execute tasks."],
    )

    messages = convert_node_input_to_messages(handoff)

    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"
    assert "## Node Handoff" in messages[0]["content"]
    assert "task_assessor" in messages[0]["content"]
    assert "task_analyzer" in messages[0]["content"]
    assert "Analyze selected unfinished work." in messages[0]["content"]
    assert "Do not execute tasks." in messages[0]["content"]
