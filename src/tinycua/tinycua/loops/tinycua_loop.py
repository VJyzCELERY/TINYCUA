"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.config.system_prompt import SystemPromptBuilder
from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class TinyCUALoop(BaseLoop):
    """Execution loop for TinyCUA agents.

    Extends the SDK BaseLoop with node-based execution, session management,
    chat history recording, message merging, tool scoping, and streaming.
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
            queue: Node queue for execution. Created if not provided.
            session_config: Session configuration to apply.
            max_iterations: Maximum loop iterations before forced stop.
            default_terminal_node: Default terminal node for ensure_terminal() bootstrap.
        """
        super().__init__(max_iterations=max_iterations)
        self.root_session = root_session or Session()
        self.session_config = session_config
        self.default_terminal_node = default_terminal_node

        if queue is not None:
            self.queue = queue
        else:
            query_analyst = TinyCUAQueryAnalystNode()
            response_node = ResponseNode()
            self.queue = NodeQueue(items=[query_analyst, response_node])

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Execute the loop with node-based execution.

        Merges SDK messages into root_session.input_context, then
        iterates through the node queue executing each node via
        agent._call_llm().

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
        # Merge SDK messages into root session input context (FR-005)
        # Note: User messages are NOT recorded in chat_history here because
        # they are already stored in input_context and passed to nodes via
        # _build_node_messages(). Recording them in chat_history as well would
        # cause duplication when include_chat_history=True.
        self.root_session.input_context = list(messages)

        # Ensure terminal safety at queue bootstrap
        if self.default_terminal_node is not None:
            self.queue.ensure_terminal(self.default_terminal_node)

        if stream:
            return self._run_stream(agent, tools, override_instructions)

        return await self._run_sync(agent, tools, override_instructions)

    async def _run_sync(
        self,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> str:
        """Run in non-streaming mode: iterate through node queue.

        For each node, builds messages, calls agent._call_llm(),
        records chat_history and session_context, and advances the queue.

        Args:
            agent: The agent executing.
            tools: Available tools.
            override_instructions: Optional instructions override.

        Returns:
            The final response content string.
        """
        last_content = ""

        while not self.queue.is_empty():
            node = self.queue.current
            if node is None:
                break

            content = await self._execute_node(
                node, agent, tools, override_instructions,
            )
            last_content = content

            # Stop at terminal nodes — do not advance past them
            if node.is_terminal:
                break

            # Advance queue (calls propagate on current node)
            self.queue.advance()

        return last_content

    def _prepare_node(
        self,
        node: Node,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[Tool]]:
        """Prepare a node for execution: attach session, build messages, resolve tools.

        Args:
            node: The node to prepare.
            tools: Available tools from the agent.
            override_instructions: Optional instructions override.

        Returns:
            Tuple of (messages, resolved_tools) ready for LLM call.
        """
        node.ensure_session(self.root_session)
        messages = self._build_node_messages(node, override_instructions)
        resolved_tools = node.config.tool_policy.resolve_tools(tools)
        return messages, resolved_tools

    def _record_node_output(
        self,
        node: Node,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Record node output in chat_history and session_context.

        Args:
            node: The node that produced output.
            content: The response content string.
            tool_calls: Optional list of tool call dicts.
        """
        if content:
            self.root_session.chat_history.append({
                "role": "assistant",
                "content": content,
            })

        llm_result = LLMResult(
            content=content,
            role="assistant",
            tool_calls=tool_calls or [],
        )
        node.record_output(llm_result)

    async def _run_stream(
        self,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run in streaming mode: iterate through node queue, yield events.

        For each node, builds messages, calls agent._call_llm(stream=True),
        yields stream events, records chat_history and session_context.

        Args:
            agent: The agent executing.
            tools: Available tools.
            override_instructions: Optional instructions override.

        Yields:
            Stream event dicts from the LLM.
        """
        while not self.queue.is_empty():
            node = self.queue.current
            if node is None:
                break

            messages, resolved_tools = self._prepare_node(
                node, tools, override_instructions,
            )

            # Stream from agent._call_llm() and yield events
            content_parts: list[str] = []
            collected_tool_calls: list[dict[str, Any]] = []
            async for event in agent._call_llm(messages, resolved_tools, stream=True):  # type: ignore[arg-type]
                if event.get("type") == "response.output_text.delta":
                    content_parts.append(event.get("delta", ""))
                if event.get("type") == "response.tool_call":
                    collected_tool_calls.append(event)
                yield event

            combined = "".join(content_parts)
            self._record_node_output(node, combined, collected_tool_calls)

            # Stop at terminal nodes — do not advance past them
            if node.is_terminal:
                break

            # Advance queue (calls propagate on current node)
            self.queue.advance()

    async def _execute_node(
        self,
        node: Node,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> str:
        """Execute a single node by building messages and calling agent._call_llm().

        Builds messages from node instruction and session context,
        resolves tools via NodeToolPolicy, calls agent._call_llm(),
        records chat_history and session_context.

        For QueryAnalyst nodes, checks for mandatory_passthrough
        before making an LLM call. If a valid MandatoryPassthrough
        directive is present, short-circuits to passthrough without
        LLM classification (FR-005/FR-006).

        Args:
            node: The node to execute.
            agent: The agent executing.
            tools: Available tools from the agent.
            override_instructions: Optional instructions override.

        Returns:
            The response content string.
        """
        # Precheck: mandatory_passthrough for QueryAnalyst nodes (FR-005/FR-006)
        if isinstance(node, TinyCUAQueryAnalystNode):
            node.ensure_session(self.root_session)
            input_data = self._build_query_analyst_input()
            mandatory = node.check_mandatory_passthrough(input_data)
            if mandatory is not None:
                logger.info(
                    "node=%s mandatory_passthrough detected in loop, bypassing LLM",
                    node.node_id,
                )
                # Record passthrough decision
                passthrough_content = (
                    f"[Passthrough] target={mandatory.target_node_id} "
                    f"reason={mandatory.reason}"
                )
                self._record_node_output(node, passthrough_content)
                # Dispatch route (passthrough handler)
                from tinycua.config.types import LLMResult
                from tinycua.loops.node import DecisionResult
                from tinycua.models.classification import PASSTHROUGH

                decision = DecisionResult(
                    route_label=PASSTHROUGH,
                    analysis_response=LLMResult(content="", role="assistant"),
                    classification_response=LLMResult(
                        content=PASSTHROUGH, role="assistant"
                    ),
                )
                node.on_complete(self.queue, decision)
                return passthrough_content

        messages, resolved_tools = self._prepare_node(
            node, tools, override_instructions,
        )

        response = await agent._call_llm(messages, resolved_tools)  # type: ignore[arg-type]
        content = response.get("content") or ""

        self._record_node_output(node, content, response.get("tool_calls"))

        return content

    def _build_query_analyst_input(self) -> NodeInput:
        """Build a NodeInput from the root session's input context for mandatory_passthrough checks.

        Converts the current input context messages into a NodeInput
        so QueryAnalyst can inspect metadata for mandatory_passthrough.

        Returns:
            NodeInput constructed from the root session input context.
        """
        messages: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        if self.root_session.input_context:
            for msg in self.root_session.input_context:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
                if "metadata" in msg:
                    metadata.update(msg["metadata"])
        return NodeInput(input_type="continuation", messages=messages, metadata=metadata)

    def _build_node_messages(
        self,
        node: Node,
        override_instructions: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build messages for a node's LLM call.

        Assembles system instruction (with override support),
        session context, chat history, and node-specific instruction.

        Args:
            node: The node to build messages for.
            override_instructions: Optional instructions override.

        Returns:
            List of message dictionaries for the LLM call.
        """
        messages: list[dict[str, Any]] = []

        # Build system message via SystemPromptBuilder
        builder = SystemPromptBuilder()
        instruction = node.build_instruction(override_instructions)
        if instruction:
            builder.add_static(instruction)

        system_msg = builder.build()
        if system_msg["content"]:
            messages.append(system_msg)

        # Add session context if policy says so
        if (
            node.config.message_policy.include_session_context
            and self.root_session.session_context
        ):
            messages.extend(
                {
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in self.root_session.session_context
            )

        # Add chat history if policy says so
        if node.config.message_policy.include_chat_history and self.root_session.chat_history:
            messages.extend(
                {
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in self.root_session.chat_history
            )

        # Add input context (merged SDK messages) as continuation
        if self.root_session.input_context:
            messages.extend(
                {
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in self.root_session.input_context
            )

        return messages
