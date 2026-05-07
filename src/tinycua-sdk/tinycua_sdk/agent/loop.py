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
        stream: str = "off",
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Execute the agent loop with optional streaming.

        Args:
            agent: The agent to execute.
            messages: List of message dicts.
            tools: List of available tools.
            override_instructions: Optional instructions override.
            stream: Streaming mode - 'off', 'token', 'event', or 'all'.

        Returns:
            Final response string when stream='off', or an async iterator
            of event dicts when streaming.
        """
        if stream == "off":
            return await self._run_sync(agent, messages, tools, override_instructions)
        return self._run_stream(agent, messages, tools, override_instructions, stream)

    async def _run_sync(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> str:
        """Synchronous execution loop (stream='off')."""
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
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content or "",
                }
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
                            tool_result = await ToolExecutor.execute(
                                tool, arguments, agent
                            )
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
            else:
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
        stream_mode: str = "token",
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming execution loop.

        Args:
            agent: The agent to execute.
            messages: List of message dicts.
            tools: List of available tools.
            override_instructions: Optional instructions override.
            stream_mode: Streaming mode - 'token', 'event', or 'all'.

        Yields:
            Event dicts filtered by stream_mode.
        """
        system_msg = self._build_system_message(agent, override_instructions)
        working_messages = [system_msg] + messages

        yield {"type": "response.created"}

        tool_call_count = 0

        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                break

            content_parts, tool_calls_buffer, tool_calls_list = await self._stream_llm(
                agent,
                working_messages,
                tools,
                stream_mode,
            )

            combined_content = "".join(content_parts)
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": combined_content,
            }
            if tool_calls_list:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in tool_calls_list
                ]
            working_messages.append(assistant_msg)

            for chunk in tool_calls_buffer:
                if stream_mode in ("token", "all"):
                    yield chunk

            if tool_calls_list:
                tool_call_count, tool_events = await self._execute_tools_stream(
                    agent,
                    tools,
                    tool_calls_list,
                    tool_call_count,
                    working_messages,
                    stream_mode,
                )
                for event in tool_events:
                    yield event
            else:
                break

        yield {"type": "response.completed"}

    async def _stream_llm(
        self,
        agent: Agent,
        working_messages: list[dict],
        tools: list[Tool],
        stream_mode: str,
    ) -> tuple[list[str], list[dict], list[dict[str, Any]]]:
        """Stream LLM response and accumulate data.

        Returns:
            Tuple of (content_parts, content_delta_events, tool_calls_list).
        """
        llm_stream = await agent._call_llm(working_messages, tools, stream=True)
        content_parts: list[str] = []
        content_delta_events: list[dict] = []
        tool_calls_buffer: dict[str, dict[str, Any]] = {}

        async for chunk in llm_stream:
            chunk_type = chunk.get("type", "")
            if chunk_type == "response.output_text.delta":
                content_parts.append(chunk.get("delta", ""))
                if stream_mode in ("token", "all"):
                    content_delta_events.append(chunk)
            elif chunk_type == "response.tool_call.delta":
                tc_id = chunk.get("id", "")
                if tc_id not in tool_calls_buffer:
                    tool_calls_buffer[tc_id] = {
                        "id": tc_id,
                        "index": len(tool_calls_buffer),
                        "name": chunk.get("name", ""),
                        "arguments": chunk.get("arguments", ""),
                    }
                else:
                    tool_calls_buffer[tc_id]["arguments"] += chunk.get("arguments", "")

        return content_parts, content_delta_events, list(tool_calls_buffer.values())

    async def _execute_tools_stream(
        self,
        agent: Agent,
        tools: list[Tool],
        tool_calls_list: list[dict[str, Any]],
        tool_call_count: int,
        working_messages: list[dict],
        stream_mode: str,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Execute tool calls and return events for streaming.

        Args:
            agent: The agent to execute.
            tools: List of available tools.
            tool_calls_list: List of accumulated tool call data.
            tool_call_count: Current tool call count.
            working_messages: Current message list (mutated in place).
            stream_mode: Streaming mode for filtering.

        Returns:
            Tuple of (updated tool_call_count, list of event dicts).
        """
        events: list[dict[str, Any]] = []
        for tc in tool_calls_list:
            if tool_call_count >= agent.policy.max_tool_calls:
                break

            tool_name = tc["name"]
            try:
                arguments = json.loads(tc["arguments"])
            except json.JSONDecodeError as e:
                tool_call_count += 1
                tool_result = {
                    "error": f"Failed to parse arguments for tool '{tool_name}': {e}"
                }
                events.extend(
                    self._build_tool_events(tc, tool_name, tool_result, stream_mode)
                )
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

            events.extend(
                self._build_tool_events(tc, tool_name, tool_result, stream_mode)
            )
            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tool_name,
                    "content": str(tool_result),
                }
            )

        return tool_call_count, events

    @staticmethod
    def _build_tool_events(
        tc: dict[str, Any],
        tool_name: str,
        tool_result: Any,
        stream_mode: str,
    ) -> list[dict[str, Any]]:
        """Build tool call/output event dicts for the given stream_mode.

        Args:
            tc: Tool call data dict.
            tool_name: Name of the tool.
            tool_result: Result from tool execution.
            stream_mode: Streaming mode for filtering.

        Returns:
            List of event dicts to yield.
        """
        events: list[dict[str, Any]] = []
        if stream_mode in ("event", "all"):
            events.append(
                {
                    "type": "response.output_item.added",
                    "item": {
                        "type": "tool_call",
                        "name": tool_name,
                        "arguments": tc["arguments"],
                    },
                }
            )
            events.append(
                {
                    "type": "response.output_item.added",
                    "item": {
                        "type": "tool_output",
                        "name": tool_name,
                        "output": str(tool_result),
                    },
                }
            )
        return events

    @staticmethod
    def _last_assistant_content(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content") or ""
        return ""


__all__ = ["BaseLoop"]
