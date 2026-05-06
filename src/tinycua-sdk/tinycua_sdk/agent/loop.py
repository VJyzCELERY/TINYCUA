"""Agent execution loop."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import ToolExecutor

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool


class BaseLoop:
    """Standard tool-calling execution loop."""

    def __init__(self, max_iterations: int = 5) -> None:
        self.max_iterations = max_iterations

    def _build_system_message(
        self, agent: Agent, override_instructions: str | None = None
    ) -> dict:
        parts = []
        instructions = override_instructions or agent.instructions
        if instructions:
            parts.append(instructions)
        for skill in agent.skills:
            parts.append(f"[{skill.name}]\n{skill.instructions}")
        return {"role": "system", "content": "\n\n".join(parts)}

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> str:
        """Execute the agent loop with tool calling and cancellation support."""
        system_msg = self._build_system_message(agent, override_instructions)
        messages = [system_msg] + messages

        tool_call_count = 0

        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                raise asyncio.CancelledError()

            if tool_call_count >= agent.policy.max_tool_calls:
                break

            response = await agent._call_llm(messages, tools)

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.get("content") or "",
            }
            if response.get("tool_calls"):
                assistant_msg["tool_calls"] = response["tool_calls"]
            messages.append(assistant_msg)

            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    arguments = json.loads(tc["function"]["arguments"])

                    tool = next(
                        (t for t in tools if t.name == tool_name), None
                    )
                    if tool is None:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        result = await ToolExecutor.execute(
                            tool, arguments, agent
                        )
                        tool_call_count += 1

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": str(result),
                    })
            else:
                return response.get("content") or ""

        return messages[-1].get("content") or "[max iterations reached]"
