"""Agent execution loop."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
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
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Execute the agent loop with optional streaming.

        Args:
            agent: The agent to execute.
            messages: List of message dicts.
            tools: List of available tools.
            override_instructions: Optional instructions override.
            stream: When True, returns an async iterator of raw SSE events.

        Returns:
            Final response string when stream=False, or an async iterator
            of event dicts when streaming.
        """
        if not stream:
            return await self._run_sync(agent, messages, tools, override_instructions)
        return self._run_stream(agent, messages, tools, override_instructions)

    async def _run_sync(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> str:
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
            if not isinstance(response, dict):
                raise TypeError(
                    f"Expected dict from _call_llm(stream=False), got {type(response).__name__}"
                )
            content = response.get("content")
            tool_calls = response.get("tool_calls")
            if tool_calls:
                executed_tool_calls: list[dict[str, Any]] = []
                tool_result_messages: list[dict[str, Any]] = []
                for tc in tool_calls:
                    if tool_call_count >= agent.policy.max_tool_calls:
                        max_tool_calls_reached = True
                        break

                    tool_name = tc["function"]["name"]
                    executed_tool_calls.append(tc)

                    try:
                        arguments = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError as e:
                        tool_call_count += 1
                        tool_result = {
                            "error": f"Failed to parse arguments for tool '{tool_name}': {e}"
                        }
                        tool_result_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": tool_name,
                                "content": str(tool_result),
                            }
                        )
                        continue

                    tool = next((t for t in tools if t.name == tool_name), None)
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

                    tool_result_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tool_name,
                            "content": str(tool_result),
                        }
                    )

                if content or executed_tool_calls:
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": content or "",
                    }
                    if executed_tool_calls:
                        assistant_msg["tool_calls"] = executed_tool_calls
                    working_messages.append(assistant_msg)
                working_messages.extend(tool_result_messages)
            else:
                if content:
                    working_messages.append({"role": "assistant", "content": content})
                return content or ""

        last_assistant = self._last_assistant_content(working_messages)
        if max_tool_calls_reached:
            return last_assistant or "[max tool calls reached]"
        return last_assistant or "[max iterations reached]"

    async def _run_stream(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        system_msg = self._build_system_message(agent, override_instructions)
        working_messages = [system_msg] + messages

        yield {"type": "response.created"}

        tool_call_count = 0
        cumulative_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        finish_reason = "completed"

        try:
            for _ in range(self.max_iterations):
                if agent.is_cancelled:
                    yield {"type": "response.cancelled"}
                    break

                if tool_call_count >= agent.policy.max_tool_calls:
                    finish_reason = "max_tool_calls"
                    break

                content_parts: list[str] = []
                tool_calls_buffer: dict[int, dict[str, Any]] = {}
                content_item_id: list[str] = [""]

                llm_stream = await agent._call_llm(working_messages, tools, stream=True)
                if not isinstance(llm_stream, AsyncIterator):
                    raise TypeError(
                        f"Expected AsyncIterator from _call_llm(stream=True), "
                        f"got {type(llm_stream).__name__}"
                    )

                async for chunk in llm_stream:
                    yield chunk
                    self._accumulate_chunk(chunk, content_parts, tool_calls_buffer, content_item_id, cumulative_usage)

                combined_content = "".join(content_parts)
                tool_calls_list = list(tool_calls_buffer.values())
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": combined_content,
                }

                if tool_calls_list:
                    (
                        tool_call_count,
                        executed_tool_calls,
                        assistant_index,
                    ) = await self._execute_tools_stream(
                        agent,
                        tools,
                        tool_calls_list,
                        tool_call_count,
                        working_messages,
                    )
                    if executed_tool_calls:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in executed_tool_calls
                        ]
                        working_messages.insert(assistant_index, assistant_msg)
                else:
                    working_messages.append(assistant_msg)
                    break
            else:
                finish_reason = "max_iterations"
        except Exception as e:
            yield {
                "type": "response.failed",
                "error": {"message": str(e)},
            }
            yield {"type": "error", "error": {"message": str(e)}}
            return

        if cumulative_usage["total_tokens"] > 0:
            yield {"type": "response.usage", "usage": dict(cumulative_usage)}
        if not agent.is_cancelled:
            yield {"type": "response.completed", "finish_reason": finish_reason}

    async def _execute_tools_stream(
        self,
        agent: Agent,
        tools: list[Tool],
        tool_calls_list: list[dict[str, Any]],
        tool_call_count: int,
        working_messages: list[dict],
    ) -> tuple[int, list[dict[str, Any]], int]:
        assistant_index = len(working_messages)
        executed_tool_calls: list[dict[str, Any]] = []
        for tc in tool_calls_list:
            if tool_call_count >= agent.policy.max_tool_calls:
                break

            tool_name = tc["name"]
            executed_tool_calls.append(tc)
            try:
                arguments = json.loads(tc["arguments"])
            except json.JSONDecodeError as e:
                tool_call_count += 1
                tool_result = {
                    "error": f"Failed to parse arguments for tool '{tool_name}': {e}"
                }
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": str(tool_result),
                    }
                )
                continue

            tool = next((t for t in tools if t.name == tool_name), None)
            if tool is None:
                tool_result = {"error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    tool_result = await ToolExecutor.execute(tool, arguments, agent)
                except Exception as e:
                    tool_result = {"error": f"Tool execution failed: {e}"}
            tool_call_count += 1

            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tool_name,
                    "content": str(tool_result),
                }
            )

        return tool_call_count, executed_tool_calls, assistant_index

    @staticmethod
    def _accumulate_chunk(
        chunk: dict[str, Any],
        content_parts: list[str],
        tool_calls_buffer: dict[int, dict[str, Any]],
        content_item_id: list[str],
        cumulative_usage: dict[str, int],
    ) -> None:
        chunk_type = chunk.get("type", "")
        if chunk_type == "response.output_text.delta":
            if not content_item_id[0]:
                content_item_id[0] = chunk.get("item_id", "")
            content_parts.append(chunk.get("delta", ""))
        elif chunk_type == "response.tool_call.delta":
            tc_index = chunk.get("index", len(tool_calls_buffer))
            if tc_index not in tool_calls_buffer:
                tool_calls_buffer[tc_index] = {
                    "id": chunk.get("id", ""),
                    "index": tc_index,
                    "name": chunk.get("name", ""),
                    "arguments": chunk.get("arguments", ""),
                }
            else:
                buf = tool_calls_buffer[tc_index]
                if chunk.get("id"):
                    buf["id"] = chunk["id"]
                if chunk.get("name"):
                    buf["name"] = chunk["name"]
                buf["arguments"] += chunk.get("arguments", "")
        elif chunk_type == "response.usage":
            usage = chunk.get("usage", {})
            for key in cumulative_usage:
                cumulative_usage[key] += usage.get(key, 0)

    @staticmethod
    def _last_assistant_content(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content") or ""
        return ""


__all__ = ["BaseLoop"]
