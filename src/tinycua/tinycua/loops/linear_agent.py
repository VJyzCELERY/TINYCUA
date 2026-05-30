"""LinearAgentLoop — ReAct execution with single input→output contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

__all__ = ["LinearAgentLoop", "LinearAgentConfig"]


@dataclass
class LinearAgentConfig:
    """Configuration for :class:`LinearAgentLoop`.

    Attributes:
        system_prompt_template: Agent-specific system prompt override.
        max_iterations: Maximum ReAct iterations.
        enable_streaming: Whether streaming is enabled by default.
    """

    system_prompt_template: str = ""
    max_iterations: int = 5
    enable_streaming: bool = True


class LinearAgentLoop(BaseLoop):
    """ReAct execution loop with single input→output contract.

    No internal routing branches — a single pass of think → act →
    observe → repeat for a configured number of iterations.

    Used by Task Analyzer, Task Executor, Task Assessor, and Primary Agent
    with different tool sets and system prompts.

    Args:
        max_iterations: Maximum ReAct iterations (default 5).
        system_prompt_template: Optional system prompt override sent to
            the LLM in addition to the agent's instructions.
        shallow_task_list: Optional list of task dicts for scope awareness.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        system_prompt_template: str = "",
        shallow_task_list: list[dict] | None = None,
    ) -> None:
        super().__init__(max_iterations=max_iterations)
        self.system_prompt_template = system_prompt_template
        self.shallow_task_list: list[dict] | None = shallow_task_list

    def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        stream: bool = False,
        *,
        input_data: str | dict,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Run the linear agent loop.

        When ``stream=False`` (default), returns a coroutine that resolves
        to the final output string — call with ``await``.

        When ``stream=True``, returns an async iterator of SSE event dicts
        — use ``async for`` to consume.

        Args:
            agent: The agent executing the loop.
            messages: Existing conversation messages.
            tools: Available tools for the agent to use.
            stream: When True, yields SSE events instead of returning a string.
            input_data: The input to process. Can be a string or dict
                (serialized to string).

        Returns:
            A coroutine resolving to a string when ``stream=False``, or an
            async iterator of stream events when ``stream=True``.
        """
        input_str = input_data if isinstance(input_data, str) else str(input_data)

        working: list[dict] = [self.build_system_message(agent)]
        if self.system_prompt_template:
            working.append({"role": "system", "content": self.system_prompt_template})
        if self.shallow_task_list:
            working.append({
                "role": "system",
                "content": f"Task context:\n{self._format_task_list(self.shallow_task_list)}",
            })
        working.extend(messages)
        working.append({"role": "user", "content": input_str})

        if stream:
            return self._run_stream_linear(agent, working, tools)

        return self._run_sync_linear(agent, working, tools)

    async def _run_sync_linear(
        self,
        agent: Agent,
        working: list[dict],
        tools: list[Tool],
    ) -> str:
        """Execute the ReAct loop synchronously."""
        tool_call_count = 0
        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                from asyncio import CancelledError
                raise CancelledError

            if tool_call_count >= agent.policy.max_tool_calls:
                return self.last_assistant_content(working) or "[max tool calls reached]"

            response: dict = await agent._call_llm(working, tools)  # type: ignore[arg-type]

            if response.get("tool_calls"):
                tool_call_count, max_reached = await self.process_tool_calls(
                    agent, tools, response["tool_calls"], working,  # type: ignore[arg-type]
                    tool_call_count, response.get("content") or "",
                )
                if max_reached:
                    return self.last_assistant_content(working) or "[max tool calls reached]"
            else:
                content = response.get("content", "")
                if content:
                    working.append({"role": "assistant", "content": content})
                return content or ""

        return self.last_assistant_content(working) or "[max iterations reached]"

    async def _run_stream_linear(
        self,
        agent: Agent,
        working: list[dict],
        tools: list[Tool],
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the ReAct loop with streaming."""
        tool_call_count = 0
        cumulative_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        usage_settled_ids: set[str] = set()
        finish_reason = "completed"
        skip_complete = False
        created_emitted = False

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
                    break

                content_parts: list[str] = []
                tool_calls_buffer: dict[str, dict[str, Any]] = {}
                should_abort = False

                llm_stream = await self._get_llm_stream(agent, working, tools)
                async for event in self.process_stream_iteration(
                    llm_stream, agent, content_parts, tool_calls_buffer,
                    cumulative_usage, usage_settled_ids,
                ):
                    if event["type"] == "response.created":
                        created_emitted = True
                    if event["type"] == "response.completed":
                        skip_complete = True
                        if event.get("finish_reason") == "tool_calls" or tool_calls_buffer:
                            continue
                    elif event["type"] in ("response.failed", "error", "response.cancelled"):
                        skip_complete = should_abort = True
                    yield event

                should_break, finish_reason, tool_call_count, skip_complete = (
                    await self._finalize_stream_iteration(
                        content_parts, tool_calls_buffer, agent, tools, working,
                        tool_call_count, should_abort, finish_reason, skip_complete,
                    )
                )
                if should_break:
                    break
            else:
                finish_reason = "max_iterations"

        except Exception as e:
            async for evt in self._handle_stream_exception(e):
                yield evt
            return

        yield {"type": "response.usage", "usage": dict(cumulative_usage)}
        if not skip_complete and not agent.is_cancelled:
            yield {"type": "response.completed", "finish_reason": finish_reason}

    @staticmethod
    def _format_task_list(task_list: list[dict]) -> str:
        """Format a shallow task list for inclusion in system prompt."""
        lines: list[str] = []
        for i, task in enumerate(task_list, 1):
            name = task.get("name", task.get("task_name", f"Task {i}"))
            desc = task.get("description", task.get("task_description", ""))
            lines.append(f"{i}. {name}")
            if desc:
                lines.append(f"   {desc}")
        return "\n".join(lines)
