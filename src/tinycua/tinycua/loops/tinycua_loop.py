"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.loops.node_queue import NodeQueue
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool


class TinyCUALoop(BaseLoop):
    """Execution loop for TinyCUA agents.

    Extends the SDK BaseLoop with TinyCUA-specific session management,
    chat history recording, and (in later milestones) node-based execution.

    For Milestone 1.1, the queue is always empty so the loop acts as a
    passthrough: it records chat history and delegates directly to the LLM.
    """

    def __init__(
        self,
        root_session: Session | None = None,
        queue: NodeQueue | None = None,
        session_config: SessionConfig | None = None,
        max_iterations: int = 50,
        default_terminal_node: Node | None = None,
    ) -> None:
        """Initialize TinyCUALoop.

        Args:
            root_session: The root session for this loop. Created if not provided.
            queue: Node queue for execution (placeholder in M1.1).
            session_config: Session configuration to apply.
            max_iterations: Maximum loop iterations before forced stop.
            default_terminal_node: Default terminal node for ensure_terminal() bootstrap.
        """
        super().__init__(max_iterations=max_iterations)
        self.root_session = root_session or Session()
        self.queue = queue or NodeQueue()
        self.session_config = session_config
        self.default_terminal_node = default_terminal_node

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Execute the loop with TinyCUA session management.

        For M1.1, records chat history and delegates directly to the LLM.
        Node execution is deferred to later milestones.

        Args:
            agent: The agent executing.
            messages: List of message dicts.
            tools: Available tools.
            override_instructions: Optional instructions override.
            stream: When True, returns an async iterator of stream events.

        Returns:
            Final response string when stream=False, or an async iterator
            of event dicts when streaming.
        """
        # Record incoming user messages in chat history
        for msg in messages:
            if msg.get("role") == "user":
                self.root_session.chat_history.append(dict(msg))

        # Ensure terminal safety at queue bootstrap
        if self.default_terminal_node is not None:
            self.queue.ensure_terminal(self.default_terminal_node)

        # Build working messages with system message
        system_msg = self.build_system_message(agent, override_instructions)
        working: list[dict[str, Any]] = [system_msg, *messages]

        if stream:
            return self._run_stream(agent, working, tools)

        return await self._run_sync(agent, working, tools)

    async def _run_sync(
        self,
        agent: Agent,
        working: list[dict[str, Any]],
        tools: list[Tool],
    ) -> str:
        """Run in non-streaming mode: call LLM, record response, return content.

        Args:
            agent: The agent executing.
            working: Working message list (system + user messages).
            tools: Available tools.

        Returns:
            The assistant's response content string.
        """
        response = await agent._call_llm(working, tools)  # type: ignore[arg-type]
        content = response.get("content") or ""

        # Record assistant response in chat history
        if content:
            self.root_session.chat_history.append({
                "role": "assistant",
                "content": content,
            })

        return content

    async def _run_stream(
        self,
        agent: Agent,
        working: list[dict[str, Any]],
        tools: list[Tool],
    ) -> AsyncIterator[dict[str, Any]]:
        """Run in streaming mode: yield events, record accumulated content.

        Args:
            agent: The agent executing.
            working: Working message list (system + user messages).
            tools: Available tools.

        Yields:
            Stream event dicts from the LLM.
        """
        content_parts: list[str] = []

        async for event in agent._call_llm(working, tools, stream=True):  # type: ignore[arg-type]
            # Accumulate text deltas for chat history
            if event.get("type") == "response.output_text.delta":
                content_parts.append(event.get("delta", ""))
            yield event

        # Record accumulated content in chat history
        combined = "".join(content_parts)
        if combined:
            self.root_session.chat_history.append({
                "role": "assistant",
                "content": combined,
            })
