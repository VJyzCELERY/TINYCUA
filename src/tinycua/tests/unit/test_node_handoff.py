"""NodeHandoff transport tests."""

from __future__ import annotations

from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.node_input import convert_node_input_to_messages
from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import TinyCUATaskAssessorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.tools.handoff_tools import NodeHandoffTool


def test_node_handoff_describes_cross_agent_communication() -> None:
    """The tool explains that its recipient is a different agent."""
    assert "different agent" in NodeHandoffTool().description.lower()


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
    assert "## Relevant context" in messages[0]["content"]
    assert "Node Handoff" not in messages[0]["content"]
    assert "Analyze selected unfinished work." in messages[0]["content"]
    assert "Do not execute tasks." in messages[0]["content"]


def test_tool_transcript_records_truncated_input_arguments() -> None:
    """Tool transcripts expose bounded call arguments, including handoffs."""
    loop = TinyCUALoop()
    node = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor"),
    )
    instruction = "x" * 5_000

    loop._record_tool_result_transcripts(
        node,
        [{"name": "node_handoff", "outcome": {"success": True}}],
        [{"function": {"name": "node_handoff", "arguments": {"instruction": instruction}}}],
    )

    content = loop.get_transcript_events()[-1]["content"]
    assert '"input"' in content
    assert '"instruction"' in content
    assert "…[truncated]" in content
