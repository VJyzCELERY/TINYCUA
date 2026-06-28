"""Provider-compatible tool result feedback contracts."""

from __future__ import annotations

from unittest.mock import MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy
from tinycua.config.types import Tool
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop


class EchoTool(Tool):
    """Simple deterministic test tool."""

    def __init__(self) -> None:
        super().__init__(name="echo")

    def __call__(self, text: str) -> str:
        return f"tool saw {text}"


async def test_tool_results_are_fed_back_to_followup_llm_call() -> None:
    """A tool call is followed by a continuation call containing tool output."""
    terminal = ResponseNode(
        config=NodeConfigBase(tool_policy=NodeToolPolicy(include_agent_tools="all"))
    )
    queue = NodeQueue(items=[terminal])
    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.tool_permissions = {}
    agent.approval_workflow = None
    captured_messages: list[list[dict]] = []

    async def call_llm(messages, tools, stream=False):
        captured_messages.append(list(messages))
        if len(captured_messages) == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "echo", "arguments": '{"text": "hello"}'},
                    }
                ],
            }
        assert any(message.get("role") == "tool" and "tool saw hello" in message.get("content", "") for message in messages)
        return {"content": "final after tool", "tool_calls": []}

    agent._call_llm = call_llm

    result = await loop.run(
        agent,
        [{"role": "user", "content": "use the echo tool"}],
        tools=[EchoTool()],
        stream=False,
    )

    assert result == "final after tool"
    assert len(captured_messages) == 2
