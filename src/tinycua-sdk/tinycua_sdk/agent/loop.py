"""Agent execution loop."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from tinycua_sdk.agent.executor import ToolExecutor

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool




class BaseLoop:
    """Standard tool-calling execution loop."""

    def __init__(self, max_iterations: int = 5) -> None:
        self.max_iterations = max_iterations

    def build_system_message(
        self, agent: Agent, override_instructions: str | None = None,
    ) -> dict[str, str]:
        """Build the system message from agent instructions and skills.

        Args:
            agent: The agent with instructions and skills.
            override_instructions: Optional instructions to use instead
                of agent.instructions.

        Returns:
            A message dict with ``role: system``.
        """
        parts = []
        instructions = override_instructions or agent.instructions
        if instructions:
            parts.append(instructions)
        for skill in agent.skills:
            parts.append(f"[{skill.name}]\n{skill.instructions}")
        return {"role": "system", "content": "\n\n".join(parts)}

    async def process_tool_calls(
        self,
        agent: Agent,
        tools: list[Tool],
        tool_calls: list[dict[str, Any]],
        working_messages: list[dict[str, Any]],
        tool_call_count: int,
        assistant_content: str = "",
    ) -> tuple[int, bool]:
        """Process LLM tool calls: parse arguments, execute tools, append messages.

        Checks ``agent.is_cancelled`` before every tool call and after
        each tool execution so that cancellation is observed promptly.
        Appends an assistant message (with ``assistant_content``) before
        ``function_call`` / ``function_call_output`` messages.  This method
        mutates ``working_messages`` in place.

        Args:
            agent: The agent executing the loop.
            tools: List of available tools.
            tool_calls: Tool call dicts from the LLM response.
            working_messages: Message list (mutated in place).
            tool_call_count: Current tool call counter.
            assistant_content: Optional assistant text to prepend.

        Returns:
            Tuple of ``(updated_tool_call_count, max_tool_calls_reached)``.
        """
        max_tool_calls_reached = False
        executed_tool_calls: list[dict[str, Any]] = []
        tool_result_messages: list[dict[str, Any]] = []

        for tc in tool_calls:
            if agent.is_cancelled:
                raise asyncio.CancelledError
            if tool_call_count >= agent.policy.max_tool_calls:
                max_tool_calls_reached = True
                break

            tool_name = tc["name"]
            executed_tool_calls.append(tc)

            try:
                arguments = json.loads(tc["arguments"])
            except json.JSONDecodeError as e:
                tool_call_count += 1
                tool_result = {
                    "error": f"Failed to parse arguments for tool '{tool_name}': {e}",
                }
                tool_result_messages.append(
                    {
                        "role": "tool_result",
                        "call_id": _resolve_call_id(tc),
                        "content": str(tool_result),
                    },
                )
                continue

            tool = next((t for t in tools if t.name == tool_name), None)
            if tool is None:
                tool_result = {"error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    tool_result = await ToolExecutor.execute(tool, arguments, agent)
                    if agent.is_cancelled:
                        raise asyncio.CancelledError
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    tool_result = {"error": f"Tool execution failed: {e}"}
            tool_call_count += 1

            tool_result_messages.append(
                {
                    "role": "tool_result",
                    "call_id": _resolve_call_id(tc),
                    "content": str(tool_result),
                },
            )

        if executed_tool_calls:
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": assistant_content,
            }
            working_messages.append(assistant_msg)
        working_messages.extend(tool_result_messages)

        return tool_call_count, max_tool_calls_reached

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
            stream: When True, returns an async iterator of SDK-normalized stream events.

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
        working: list[dict] = [self.build_system_message(agent, override_instructions), *messages]
        tool_call_count = 0
        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                raise asyncio.CancelledError
            if tool_call_count >= agent.policy.max_tool_calls:
                return self.last_assistant_content(working) or "[max tool calls reached]"
            response = await agent._call_llm(working, tools)  # type: ignore[arg-type]
            if not isinstance(response, dict):
                msg = f"Expected dict from _call_llm(stream=False), got {type(response).__name__}"
                raise TypeError(
                    msg,
                )
            if response.get("tool_calls"):
                tool_call_count, max_reached = await self.process_tool_calls(
                    agent, tools, response["tool_calls"], working, tool_call_count,  # type: ignore[arg-type]
                    response.get("content") or "",
                )
                if max_reached:
                    return self.last_assistant_content(working) or "[max tool calls reached]"
            else:
                content = response.get("content")
                if content:
                    working.append({"role": "assistant", "content": content})
                return content or ""
        return self.last_assistant_content(working) or "[max iterations reached]"

    async def _run_stream(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        working: list[dict] = [self.build_system_message(agent, override_instructions), *messages]
        tool_call_count, cumulative_usage = 0, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        usage_settled_ids: set[str] = set()
        finish_reason, skip_complete, created_emitted = "completed", False, False
        try:
            for _ in range(self.max_iterations):
                if agent.is_cancelled:
                    yield {"type": "response.created"}
                    created_emitted = True
                    yield {"type": "response.cancelled"}
                    skip_complete = True
                    break
                if tool_call_count >= agent.policy.max_tool_calls:
                    finish_reason = "max_tool_calls"
                    skip_complete = False
                    break
                content_parts: list[str] = []
                tool_calls_buffer: dict[str, dict[str, Any]] = {}
                usage_settled_ids.clear()
                skip_complete = should_abort = False
                llm_stream = await self._get_llm_stream(agent, working, tools)
                async for event in self.process_stream_iteration(
                    llm_stream, agent, content_parts, tool_calls_buffer,
                    cumulative_usage, usage_settled_ids,
                ):
                    if event["type"] == "response.created":
                        created_emitted = True
                    if event["type"] == "response.completed":
                        skip_complete = True
                        # Suppress intermediate tool-call completions so
                        # consumers only see one terminal response.completed
                        # for the entire Agent.run(stream=True) call.
                        if event.get("finish_reason") == "tool_calls" or tool_calls_buffer:
                            continue
                    elif event["type"] in ("response.failed", "error", "response.cancelled"):
                        skip_complete = should_abort = True
                    yield event
                if should_abort:
                    break
                combined = "".join(content_parts)
                tool_calls_list = [
                    tc for tc in tool_calls_buffer.values()
                    if tc.get("_ready", False)
                ]
                if tool_calls_list:
                    tool_call_count, max_reached = await self.process_stream_tool_calls(
                        agent, tools, tool_calls_list, working, tool_call_count, combined,
                    )
                    if max_reached:
                        finish_reason, skip_complete = "max_tool_calls", False
                        break
                else:
                    working.append({"role": "assistant", "content": combined})
                    break
            else:
                finish_reason = "max_iterations"
        except asyncio.CancelledError:
            if not created_emitted:
                yield {"type": "response.created"}
            yield {"type": "response.cancelled"}
            skip_complete = True
        except Exception as e:
            yield {"type": "response.failed", "error": {"message": str(e)}}
            yield {"type": "error", "error": {"message": str(e)}}
            return
        yield {"type": "response.usage", "usage": dict(cumulative_usage)}
        if not skip_complete and not agent.is_cancelled:
            yield {"type": "response.completed", "finish_reason": finish_reason}

    @staticmethod
    async def _get_llm_stream(
        agent: Agent,
        working: list[dict],
        tools: list[Tool],
    ) -> AsyncIterator[dict[str, Any]]:
        """Call the LLM in streaming mode and validate the response type.

        Args:
            agent: The agent executing the loop.
            working: The working message list.
            tools: List of available tools.

        Returns:
            An async iterator of SDK-normalized stream event dicts.

        Raises:
            TypeError: If the LLM does not return an async iterator.
        """
        llm_stream = await agent._call_llm(working, tools, stream=True)  # type: ignore[arg-type]
        if not isinstance(llm_stream, AsyncIterator):
            msg = (
                f"Expected AsyncIterator from _call_llm(stream=True), got "
                f"{type(llm_stream).__name__}"
            )
            raise TypeError(
                msg,
            )
        return cast("AsyncIterator[dict[str, Any]]", llm_stream)

    async def process_stream_iteration(
        self,
        llm_stream: AsyncIterator[dict[str, Any]],
        agent: Agent,
        content_parts: list[str],
        tool_calls_buffer: dict[str, dict[str, Any]],
        cumulative_usage: dict[str, int],
        usage_settled_ids: set[str],
    ) -> AsyncIterator[dict[str, Any]]:
        """Process one LLM stream iteration, yield lifecycle and data events.

        Orchestrates first-chunk processing and stream-body iteration.
        Delegates to ``_process_first_chunk`` and ``_process_stream_body``
        to keep each method focused and testable.

        Args:
            llm_stream: The LLM stream async iterator.
            agent: The agent executing the loop.
            content_parts: List of text delta strings (appended in place).
            tool_calls_buffer: Dict of tool call key to accumulated data.
            cumulative_usage: Dict of cumulative token counts.
            usage_settled_ids: Set of response IDs whose usage has been counted.

        Yields:
            SDK-normalized stream events and synthetic lifecycle events.
        """
        events, provider_failed, in_progress_emitted = await self._process_first_chunk(
            llm_stream, agent, content_parts, tool_calls_buffer,
            cumulative_usage, usage_settled_ids,
        )
        for event in events:
            yield event
        if provider_failed:
            return

        async for event in self._process_stream_body(
            llm_stream, agent, content_parts, tool_calls_buffer,
            cumulative_usage, usage_settled_ids, in_progress_emitted,
        ):
            yield event

    async def _process_first_chunk(
        self,
        llm_stream: AsyncIterator[dict[str, Any]],
        agent: Agent,
        content_parts: list[str],
        tool_calls_buffer: dict[str, dict[str, Any]],
        cumulative_usage: dict[str, int],
        usage_settled_ids: set[str],
    ) -> tuple[list[dict[str, Any]], bool, bool]:
        """Process the first chunk from ``llm_stream``.

        Handles cancellation, empty stream, and all first-chunk event type
        routing. Accumulates the first chunk's data into the shared buffers.

        Returns:
            Tuple of (events_to_yield, provider_failed, in_progress_emitted).
            ``provider_failed`` is ``True`` when the first chunk indicates a
            provider error — the caller should return immediately without
            processing the stream body.
        """
        first_chunk, first_cancelled = await self._read_stream_chunk(
            llm_stream, agent._cancel_event,
        )
        if first_cancelled:
            if hasattr(llm_stream, "aclose"):
                await llm_stream.aclose()
            return [
                {"type": "response.created"},
                {"type": "response.cancelled"},
            ], False, False

        if first_chunk is None:
            return [
                {"type": "response.created"},
                {"type": "response.in_progress"},
            ], False, False

        chunk_type = first_chunk.get("type", "")
        events: list[dict[str, Any]] = []
        provider_failed = False
        in_progress_emitted = False

        if chunk_type == "response.created":
            events.append(first_chunk)
        elif chunk_type == "response.completed":
            events.append({"type": "response.created"})
            events.append(first_chunk)
        elif chunk_type in ("response.failed", "error"):
            provider_failed = True
            events.append({"type": "response.created"})
            events.append(first_chunk)
        elif chunk_type == "response.in_progress":
            events.append({"type": "response.created"})
            events.append(first_chunk)
            in_progress_emitted = True
        else:
            events.append({"type": "response.created"})
            events.append({"type": "response.in_progress"})
            in_progress_emitted = True
            events.append(first_chunk)

        self._accumulate_chunk(
            first_chunk, content_parts, tool_calls_buffer,
            cumulative_usage, usage_settled_ids,
        )

        return events, provider_failed, in_progress_emitted

    async def _process_stream_body(
        self,
        llm_stream: AsyncIterator[dict[str, Any]],
        agent: Agent,
        content_parts: list[str],
        tool_calls_buffer: dict[str, dict[str, Any]],
        cumulative_usage: dict[str, int],
        usage_settled_ids: set[str],
        in_progress_emitted: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Iterate through the stream body after the first chunk.

        Yields stream body events, accumulates chunk data into the shared
        buffers, tracks ``in_progress`` emission, and detects provider
        failure / cancellation.

        Args:
            llm_stream: The LLM stream async iterator.
            agent: The agent executing the loop.
            content_parts: List of text delta strings (appended in place).
            tool_calls_buffer: Dict of tool call key to accumulated data.
            cumulative_usage: Dict of cumulative token counts.
            usage_settled_ids: Set of response IDs whose usage has been counted.
            in_progress_emitted: Whether ``response.in_progress`` was already
                emitted by the first-chunk handler.

        Yields:
            SDK-normalized stream events from the stream body.
        """
        async for chunk, _ in self._iter_llm_events(
            llm_stream, agent._cancel_event,
        ):
            if chunk is None:
                break
            if chunk.get("type") == "response.in_progress":
                in_progress_emitted = True
            elif chunk.get("type") in (
                "response.completed", "response.failed", "error",
            ):
                pass
            elif not in_progress_emitted:
                yield {"type": "response.in_progress"}
                in_progress_emitted = True

            if chunk.get("type") in ("response.failed", "error"):
                yield chunk
                self._accumulate_chunk(
                    chunk, content_parts, tool_calls_buffer,
                    cumulative_usage, usage_settled_ids,
                )
                break
            yield chunk
            self._accumulate_chunk(
                chunk, content_parts, tool_calls_buffer,
                cumulative_usage, usage_settled_ids,
            )
        if agent.is_cancelled:
            yield {"type": "response.cancelled"}

    async def process_stream_tool_calls(
        self,
        agent: Agent,
        tools: list[Tool],
        tool_calls_list: list[dict[str, Any]],
        working_messages: list[dict],
        tool_call_count: int,
        combined_content: str = "",
    ) -> tuple[int, bool]:
        """Execute stream tool calls and append results to working_messages.

        Appends an assistant message (with ``combined_content``) before the
        ``function_call`` and ``function_call_output`` messages.

        Args:
            agent: The agent executing the loop.
            tools: List of available tools.
            tool_calls_list: Accumulated tool call data from LLM stream.
            working_messages: Message list (mutated in place).
            tool_call_count: Current tool call count.
            combined_content: Accumulated stream text to include in assistant msg.

        Returns:
            Tuple of ``(updated_tool_call_count, max_tool_calls_reached)``.
        """
        max_tool_calls_reached = False
        executed_tool_calls: list[dict[str, Any]] = []
        tool_result_messages: list[dict[str, Any]] = []

        for tc in tool_calls_list:
            if agent.is_cancelled:
                raise asyncio.CancelledError
            if tool_call_count >= agent.policy.max_tool_calls:
                max_tool_calls_reached = True
                break

            tool_name = tc["name"]
            executed_tool_calls.append(tc)
            try:
                arguments = json.loads(tc["arguments"])
            except json.JSONDecodeError as e:
                tool_call_count += 1
                tool_result = {
                    "error": f"Failed to parse arguments for tool '{tool_name}': {e}",
                }
                tool_result_messages.append(
                    {
                        "role": "tool_result",
                        "call_id": _resolve_call_id(tc),
                        "content": str(tool_result),
                    },
                )
                continue

            tool = next((t for t in tools if t.name == tool_name), None)
            if tool is None:
                tool_result = {"error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    tool_result = await ToolExecutor.execute(tool, arguments, agent)
                    if agent.is_cancelled:
                        raise asyncio.CancelledError
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    tool_result = {"error": f"Tool execution failed: {e}"}
            tool_call_count += 1

            tool_result_messages.append(
                {
                    "role": "tool_result",
                    "call_id": _resolve_call_id(tc),
                    "content": str(tool_result),
                },
            )

        if executed_tool_calls:
            working_messages.append(
                {"role": "assistant", "content": combined_content},
            )
        working_messages.extend(tool_result_messages)

        return tool_call_count, max_tool_calls_reached

    @staticmethod
    def _accumulate_chunk(
        chunk: dict[str, Any],
        content_parts: list[str],
        tool_calls_buffer: dict[str, dict[str, Any]],
        cumulative_usage: dict[str, int],
        usage_settled_ids: set[str],
    ) -> None:
        """Accumulate a stream chunk into content parts, tool calls buffer, and usage.

        Args:
            chunk: SDK-normalized or raw stream event dict from the LLM.
            content_parts: List of text delta strings (appended in place).
            tool_calls_buffer: Dict of tool call index to accumulated data.
            cumulative_usage: Dict of cumulative token counts (accumulated in place).
            usage_settled_ids: Set of response IDs whose usage has been counted.
        """
        chunk_type = chunk.get("type", "")
        if chunk_type == "response.output_text.delta":
            content_parts.append(chunk.get("delta", ""))
        elif chunk_type in ("response.tool_call.delta", "response.output_item.added",
                            "response.function_call_arguments.delta", "response.function_call_arguments.done",
                            "tool_call.ready"):
            _accumulate_tool_chunk(chunk, chunk_type, tool_calls_buffer)
        elif chunk_type == "response.completed":
            response_data = chunk.get("response", {})
            resp_id = response_data.get("id", "")
            usage = response_data.get("usage", {})
            if usage and resp_id not in usage_settled_ids:
                if "" in usage_settled_ids:
                    usage_settled_ids.remove("")
                    usage_settled_ids.add(resp_id)
                else:
                    _accumulate_usage(cumulative_usage, usage)
                    usage_settled_ids.add(resp_id)
        elif chunk_type == "response.usage":
            usage = chunk.get("usage", {})
            resp_id = chunk.get("response", {}).get("id", "")
            if usage and resp_id not in usage_settled_ids:
                _accumulate_usage(cumulative_usage, usage)
                usage_settled_ids.add(resp_id)

    @staticmethod
    async def _read_stream_chunk(
        llm_stream: AsyncIterator[dict[str, Any]],
        cancel_event: asyncio.Event,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Read one chunk from ``llm_stream``, raced against cancellation.

        Returns ``(chunk, False)`` on success, ``(None, True)`` when
        cancellation was requested, or ``(None, False)`` on stream
        exhaustion (``StopAsyncIteration``).
        """
        next_task: asyncio.Task[dict[str, Any] | None] = asyncio.ensure_future(
            llm_stream.__anext__(),
        )
        cancel_task = asyncio.create_task(cancel_event.wait())
        _done, pending = await asyncio.wait(
            [next_task, cancel_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        for t in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await t
        if cancel_event.is_set():
            return None, True
        try:
            return next_task.result(), False
        except StopAsyncIteration:
            return None, False

    @staticmethod
    async def _iter_llm_events(
        llm_stream: AsyncIterator[dict[str, Any]],
        cancel_event: asyncio.Event,
    ) -> AsyncIterator[tuple[dict[str, Any] | None, bool]]:
        """Yield ``(chunk, is_completed)`` from ``llm_stream``.

        Yields ``(None, False)`` on stream exhaustion. Returns (stops
        iteration) when cancellation is requested — caller checks
        ``cancel_event.is_set()`` to detect cancellation.
        """
        try:
            while True:
                chunk, cancelled = await BaseLoop._read_stream_chunk(llm_stream, cancel_event)
                if cancelled:
                    return
                if chunk is None:
                    yield None, False
                    return
                yield chunk, chunk.get("type") == "response.completed"
        finally:
            if hasattr(llm_stream, "aclose"):
                await llm_stream.aclose()

    @staticmethod
    def last_assistant_content(messages: list[dict]) -> str:
        """Get the content of the last assistant message.

        Args:
            messages: List of message dicts.

        Returns:
            The content of the last ``role: assistant`` message, or
            empty string if none found.
        """
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content") or ""
        return ""


def _accumulate_tool_chunk(
    chunk: dict[str, Any],
    chunk_type: str,
    tool_calls_buffer: dict[str, dict[str, Any]],
) -> None:
    """Accumulate tool call data from a stream chunk into the buffer.

    Args:
        chunk: SDK-normalized or raw stream event dict from the LLM.
        chunk_type: The type of the chunk event.
        tool_calls_buffer: Dict of tool call key to accumulated data (mutated in place).
    """
    if chunk_type == "response.tool_call.delta":
        tc_index = str(chunk.get("index", len(tool_calls_buffer)))
        if tc_index not in tool_calls_buffer:
            tool_calls_buffer[tc_index] = {
                "id": chunk.get("id", ""),
                "index": tc_index,
                "name": chunk.get("name", ""),
                "arguments": chunk.get("arguments", ""),
                "_ready": True,  # Legacy format: always ready
            }
        else:
            buf = tool_calls_buffer[tc_index]
            if chunk.get("id"):
                buf["id"] = chunk["id"]
            if chunk.get("name"):
                buf["name"] = chunk["name"]
            buf["arguments"] += chunk.get("arguments", "")
    elif chunk_type == "response.output_item.added":
        item_id = chunk.get("id", "")
        if item_id:
            tool_calls_buffer[item_id] = {
                "id": item_id,
                "call_id": chunk.get("call_id", ""),
                "name": chunk.get("name", ""),
                "arguments": "",
                "_ready": False,  # Progress only — not yet ready for execution
            }
    elif chunk_type == "response.function_call_arguments.delta":
        item_id = chunk.get("id", "")
        if item_id and item_id in tool_calls_buffer:
            tool_calls_buffer[item_id]["arguments"] += chunk.get("arguments", "")
    elif chunk_type == "response.function_call_arguments.done":
        item_id = chunk.get("id", "")
        if item_id and item_id in tool_calls_buffer:
            tool_calls_buffer[item_id]["arguments"] = chunk.get("arguments", "")
    elif chunk_type == "tool_call.ready":
        item_id = chunk.get("id", "")
        if item_id:
            if item_id in tool_calls_buffer:
                tool_calls_buffer[item_id].update({
                    "call_id": chunk.get("call_id", tool_calls_buffer[item_id].get("call_id", "")),
                    "name": chunk.get("name", tool_calls_buffer[item_id].get("name", "")),
                    "arguments": chunk.get("arguments", tool_calls_buffer[item_id].get("arguments", "")),
                    "_ready": True,
                })
            else:
                tool_calls_buffer[item_id] = {
                    "id": item_id,
                    "call_id": chunk.get("call_id", ""),
                    "name": chunk.get("name", ""),
                    "arguments": chunk.get("arguments", ""),
                    "_ready": True,
                }


def _resolve_call_id(tc: dict[str, Any]) -> str:
    """Resolve ``call_id`` from a tool-call dict with fallback to ``id``.

    Args:
        tc: A tool-call dict that may contain ``call_id`` and/or ``id``.

    Returns:
        The resolved call identifier.

    Raises:
        ValueError: If neither ``call_id`` nor ``id`` is present.
    """
    call_id = tc.get("call_id") or tc.get("id")
    if not call_id:
        msg = "Tool call is missing both 'call_id' and 'id'"
        raise ValueError(msg)
    return call_id


def _usage_int(value: Any) -> int:
    """Convert a token count value to int, treating ``None`` as zero.

    Args:
        value: A token count that may be ``int`` or ``None``.

    Returns:
        The value if it is an ``int``, otherwise ``0``.
    """
    return value if isinstance(value, int) else 0


def _accumulate_usage(
    cumulative: dict[str, int],
    usage: dict[str, Any],
) -> None:
    """Accumulate usage dict into cumulative counters with key normalization.

    Normalises both Responses API keys (``input_tokens``, ``output_tokens``)
    and Chat Completions keys (``prompt_tokens``, ``completion_tokens``) into
    the SDK's canonical ``input_tokens`` / ``output_tokens`` / ``total_tokens``.
    Handles schema-permitted ``None`` values by treating them as zero.

    Args:
        cumulative: Dict of cumulative token counts (mutated in place).
        usage: Usage dict from the provider response.
    """
    cumulative["input_tokens"] += _usage_int(
        usage.get("input_tokens", usage.get("prompt_tokens")),
    )
    cumulative["output_tokens"] += _usage_int(
        usage.get("output_tokens", usage.get("completion_tokens")),
    )
    cumulative["total_tokens"] += _usage_int(usage.get("total_tokens"))


__all__ = ["BaseLoop"]
