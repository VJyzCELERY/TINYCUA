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
    ) -> dict[str, str]:
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
        working_messages = [system_msg] + messages

        tool_call_count = 0
        max_tool_calls_reached = False

        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                raise asyncio.CancelledError()

            if tool_call_count >= agent.policy.max_tool_calls:
                max_tool_calls_reached = True
                break

            response = await agent._call_llm(working_messages, tools)

            content = response.get("content")
            tool_calls = response.get("tool_calls")
            if content or tool_calls:
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                working_messages.append(assistant_msg)

            if tool_calls:
                for tc in tool_calls:
                    if tool_call_count >= agent.policy.max_tool_calls:
                        break

                    tool_name = tc["function"]["name"]

                    try:
                        arguments = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError as e:
                        tool_call_count += 1
                        tool_result = {"error": f"Failed to parse arguments for tool '{tool_name}': {e}"}
                        working_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tool_name,
                            "content": str(tool_result),
                        })
                        continue

                    tool = next(
                        (t for t in tools if t.name == tool_name), None
                    )
                    if tool is None:
                        tool_result = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        try:
                            tool_result = await ToolExecutor.execute(
                                tool, arguments, agent
                            )
                        except Exception as e:
                            tool_result = {"error": f"Tool execution failed: {e}"}
                        tool_call_count += 1

                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": str(tool_result),
                    })
            else:
                return content or ""

        last_assistant = self._last_assistant_content(working_messages)
        if max_tool_calls_reached:
            return last_assistant or "[max tool calls reached]"
        return last_assistant or "[max iterations reached]"

    @staticmethod
    def _last_assistant_content(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content") or ""
        return ""


__all__ = ["BaseLoop"]
