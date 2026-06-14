"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.config.system_prompt import SystemPromptBuilder
from tinycua.models.stream_event import enrich_stream_event, make_lifecycle_event
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionNode, DecisionResult, build_messages_with_dedupe
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.propagation import (
    PropagationRule,
    finalize_terminal_output,
    propagate_on_termination,
)
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.config.types import AgentMonitor
    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike
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
        agent_monitor: AgentMonitor | None = None,
    ) -> None:
        """Initialize TinyCUALoop.

        Args:
            root_session: The root session for this loop. Created if not provided.
            queue: Node queue for execution. Created if not provided.
            session_config: Session configuration to apply.
            max_iterations: Maximum loop iterations before forced stop.
            default_terminal_node: Default terminal node for ensure_terminal() bootstrap.
            agent_monitor: Optional agent-level monitor hook for observing node execution.
        """
        super().__init__(max_iterations=max_iterations)
        self.root_session = root_session or Session()
        self.queue = queue or NodeQueue()
        self.session_config = session_config
        self.default_terminal_node = default_terminal_node
        self.agent_monitor = agent_monitor
        self._working_messages: list[dict[str, Any]] = []

    def get_working_messages(self) -> list[dict[str, Any]]:
        """Return the working messages captured during the last run.

        The working messages include system prompts, user messages,
        assistant responses, and tool calls from the most recent
        ``run()`` invocation. This is used by the transcript writer
        to produce JSONL output.

        Returns:
            List of message dicts from the last execution.
        """
        return list(self._working_messages)

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

        # Wire queue reference on QueryAnalystNode entry node
        current = self.queue.current
        if isinstance(current, TinyCUAQueryAnalystNode):
            current._queue = self.queue

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
        all_messages: list[dict[str, Any]] = []

        while not self.queue.is_empty():
            node = self.queue.current
            if node is None:
                break

            node_input = self.queue.input_for_current()
            # Capture messages built for this node for transcript
            node_messages, _ = self._prepare_node(
                node,
                tools,
                override_instructions,
            )
            all_messages.extend(node_messages)

            content, tool_calls = await self._execute_node(
                node,
                agent,
                tools,
                override_instructions,
                node_input,
            )
            last_content = content

            # Record assistant response in working messages
            if content:
                all_messages.append({"role": "assistant", "content": content})

            # Record tool calls in working messages for transcript completeness
            for tool_call in tool_calls:
                all_messages.append(
                    {
                        "role": "assistant",
                        "tool_calls": [tool_call],
                    }
                )

            # Stop at terminal nodes — do not advance past them
            if node.is_terminal:
                break

            # Advance queue (calls propagate on current node)
            self.queue.advance()

        self._working_messages = all_messages
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
    ) -> LLMResult:
        """Record node output in chat_history and session_context.

        Args:
            node: The node that produced output.
            content: The response content string.
            tool_calls: Optional list of tool call dicts.

        Returns:
            The LLMResult that was recorded.
        """
        if content:
            from tinycua.models.chat_record import ChatRecord

            self.root_session.chat_history.append(
                ChatRecord(
                    role="assistant",
                    content=content,
                    source_node_id=node.node_id,
                    source_session_id=self.root_session.session_id,
                )
            )

        llm_result = LLMResult(
            content=content,
            role="assistant",
            tool_calls=tool_calls or [],
        )
        node.record_output(llm_result)
        return llm_result

    def _emit_lifecycle_event(
        self,
        event_type: str,
        node_id: str,
        node_type: str,
        attempt: int,
        emit_lifecycle: bool,
        final_only: bool,
        is_terminal_node: bool,
        content: str | None = None,
        finish_reason: str | None = None,
    ) -> dict[str, Any] | None:
        """Create a lifecycle event if policies allow emission.

        Args:
            event_type: The lifecycle event type string.
            node_id: ID of the node.
            node_type: Class name of the node.
            attempt: Current attempt number.
            emit_lifecycle: Whether lifecycle events are enabled.
            final_only: Whether only terminal node events should emit.
            is_terminal_node: Whether this is a terminal node.
            content: Optional content for completed/error events.
            finish_reason: Optional finish reason.

        Returns:
            The lifecycle event dict, or None if emission is suppressed.
        """
        if not emit_lifecycle:
            return None

        event = make_lifecycle_event(
            event_type=event_type,  # type: ignore[arg-type]
            node_id=node_id,
            node_type=node_type,
            attempt=attempt,
            content=content,
            finish_reason=finish_reason,
        )
        if final_only and not is_terminal_node:
            return None
        return event

    def _make_error_event(
        self,
        node_id: str,
        node_type: str,
        attempt: int,
    ) -> dict[str, Any]:
        """Create a node.error lifecycle event, bypassing final_only gate.

        Error events are always emitted regardless of final_response_only policy
        because they are diagnostic signals, not intermediate output.

        Args:
            node_id: The node identifier.
            node_type: Class name of the node.
            attempt: Current attempt number.

        Returns:
            The error lifecycle event dict.
        """
        return make_lifecycle_event(
            event_type="node.error",
            node_id=node_id,
            node_type=node_type,
            attempt=attempt,
            finish_reason="error",
        )

    def _enrich_and_yield(
        self,
        event: dict[str, Any],
        include_meta: bool,
        node_id: str,
        node_type: str,
        attempt: int,
    ) -> dict[str, Any]:
        """Enrich a stream event with metadata if policy allows, then return it.

        Single centralized enrichment point — replaces scattered
        ``enrich_stream_event`` calls across lifecycle, delta, and error paths.

        Args:
            event: The stream event dict to enrich.
            include_meta: Whether metadata enrichment is enabled.
            node_id: ID of the node.
            node_type: Class name of the node.
            attempt: Current attempt number.

        Returns:
            The enriched event dict.
        """
        if include_meta:
            enrich_stream_event(event, node_id, node_type, attempt)
        return event

    def _finalize_streamed_node(
        self,
        node: Node,
        content_parts: list[str],
        collected_tool_calls: list[dict[str, Any]],
    ) -> str:
        """Finalize a streamed node: record output, fire lifecycle hooks.

        Args:
            node: The node that was streamed.
            content_parts: Accumulated text delta parts.
            collected_tool_calls: Collected tool call events.

        Returns:
            The combined content string.
        """
        combined = "".join(content_parts)
        llm_result = self._record_node_output(node, combined, collected_tool_calls)

        # Fire lifecycle hooks (same as _execute_node)
        on_complete_response: LLMResult | DecisionResult = llm_result
        if isinstance(node, DecisionNode):
            on_complete_response = DecisionResult(
                route_label=combined,
                analysis_response=llm_result,
                classification_response=llm_result,
            )
        node.on_complete(self.queue, on_complete_response)

        # Propagate context on node termination
        rule = node.config.propagation or PropagationRule()
        parent_session = self._find_parent_session(node)
        propagate_on_termination(
            node.session or self.root_session,
            parent_session,
            self.root_session,
            rule,
        )

        return combined

    async def _run_stream(
        self,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run in streaming mode: iterate through node queue, yield events.

        For each node, builds messages, calls agent._call_llm(stream=True),
        yields stream events (including lifecycle events at node boundaries),
        records chat_history and session_context.

        Lifecycle events emitted per node:
        - node.started: before agent._call_llm()
        - node.llm_call: when LLM call begins
        - node.completed: after LLM call completes successfully
        - node.error: on exception during node execution

        NodeStreamPolicy controls:
        - emit_internal_events: when False, suppresses all node.* lifecycle events
        - include_node_metadata: when True, enriches events with node_id, node_type, attempt
        - final_response_only: when True, suppresses intermediate node events (only ResponseNode events pass)

        Args:
            agent: The agent executing.
            tools: Available tools.
            override_instructions: Optional instructions override.

        Yields:
            Stream event dicts from the LLM and lifecycle transitions.
        """
        all_messages: list[dict[str, Any]] = []
        try:
            while not self.queue.is_empty():
                node = self.queue.current
                if node is None:
                    break

                # Wire queue on QueryAnalystNode before execution
                if isinstance(node, TinyCUAQueryAnalystNode):
                    node._queue = self.queue

                messages, resolved_tools = self._prepare_node(
                    node,
                    tools,
                    override_instructions,
                )
                all_messages.extend(messages)

                # Determine policy settings for this node
                policy = node.config.stream_policy
                emit_lifecycle = policy.emit_internal_events
                include_meta = policy.include_node_metadata
                final_only = policy.final_response_only
                is_terminal_node = node.is_terminal
                node_type = type(node).__name__
                attempt = 1

                # Emit node.started lifecycle event
                started = self._emit_lifecycle_event(
                    "node.started",
                    node.node_id,
                    node_type,
                    attempt,
                    emit_lifecycle,
                    final_only,
                    is_terminal_node,
                )
                if started is not None:
                    yield self._enrich_and_yield(
                        started,
                        include_meta,
                        node.node_id,
                        node_type,
                        attempt,
                    )

                # Emit node.llm_call lifecycle event
                llm_call = self._emit_lifecycle_event(
                    "node.llm_call",
                    node.node_id,
                    node_type,
                    attempt,
                    emit_lifecycle,
                    final_only,
                    is_terminal_node,
                )
                if llm_call is not None:
                    yield self._enrich_and_yield(
                        llm_call,
                        include_meta,
                        node.node_id,
                        node_type,
                        attempt,
                    )

                # Stream from agent._call_llm() and yield events
                content_parts: list[str] = []
                collected_tool_calls: list[dict[str, Any]] = []
                try:
                    async for event in agent._call_llm(
                        messages, resolved_tools, stream=True
                    ):  # type: ignore[arg-type]
                        if event.get("type") == "response.output_text.delta":
                            content_parts.append(event.get("delta", ""))
                        if event.get("type") == "response.tool_call":
                            collected_tool_calls.append(event)
                        self._enrich_and_yield(
                            event,
                            include_meta,
                            node.node_id,
                            node_type,
                            attempt,
                        )
                        if not final_only or is_terminal_node:
                            yield event
                except Exception:
                    error_event = self._make_error_event(
                        node.node_id,
                        node_type,
                        attempt,
                    )
                    yield self._enrich_and_yield(
                        error_event,
                        include_meta,
                        node.node_id,
                        node_type,
                        attempt,
                    )
                    raise

                # Finalize node: record output, fire hooks, propagate
                combined = self._finalize_streamed_node(
                    node,
                    content_parts,
                    collected_tool_calls,
                )

                # Record assistant response in working messages
                if combined:
                    all_messages.append({"role": "assistant", "content": combined})

                # Emit node.completed lifecycle event
                finish_reason = "completed" if combined else "empty"
                completed = self._emit_lifecycle_event(
                    "node.completed",
                    node.node_id,
                    node_type,
                    attempt,
                    emit_lifecycle,
                    final_only,
                    is_terminal_node,
                    content=combined,
                    finish_reason=finish_reason,
                )
                if completed is not None:
                    yield self._enrich_and_yield(
                        completed,
                        include_meta,
                        node.node_id,
                        node_type,
                        attempt,
                    )

                # Stop at terminal nodes — do not advance past them
                if node.is_terminal:
                    finalize_terminal_output(
                        node.session or self.root_session,
                        self.root_session,
                    )
                    break

                # Advance queue (calls propagate on current node)
                self.queue.advance()
        finally:
            self._working_messages = all_messages

    async def _execute_node(
        self,
        node: Node,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
        node_input: NodeInputLike | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Execute a single node by building messages and calling agent._call_llm().

        Builds messages from node instruction and session context,
        resolves tools via NodeToolPolicy, calls agent._call_llm(),
        records chat_history and session_context, then fires lifecycle
        hooks (propagate, on_complete) and transfers cross-session data.

        If an agent_monitor is configured, calls its hooks before and after
        the LLM call. The node's own monitor is called within the node's
        retry loop (via ProcessNode.__call__).

        Args:
            node: The node to execute.
            agent: The agent executing.
            tools: Available tools from the agent.
            override_instructions: Optional instructions override.
            node_input: Optional input data for the node.

        Returns:
            Tuple of (response content string, list of tool call dicts).
        """
        # Wire queue on QueryAnalystNode before execution
        if isinstance(node, TinyCUAQueryAnalystNode):
            node._queue = self.queue

        messages, resolved_tools = self._prepare_node(
            node,
            tools,
            override_instructions,
        )

        # Fire agent_monitor before-hook (if configured)
        # Note: attempt=1 at agent level because retry is node-internal.
        # Use NodeMonitor for per-attempt granularity.
        if self.agent_monitor is not None:
            try:
                self.agent_monitor.on_before_node_call(
                    node.node_id,
                    self.root_session.session_id,
                    1,  # attempt 1 at agent level
                    messages,
                    resolved_tools,
                )
            except Exception:
                logger.debug(
                    "node=%s agent_monitor_before_hook_exception",
                    node.node_id,
                    exc_info=True,
                )

        response = await agent._call_llm(messages, resolved_tools)  # type: ignore[arg-type]
        content = response.get("content") or ""

        llm_result = self._record_node_output(node, content, response.get("tool_calls"))

        # Fire agent_monitor after-hook (if configured)
        # Note: attempt=1 at agent level because retry is node-internal.
        # Use NodeMonitor for per-attempt granularity.
        if self.agent_monitor is not None:
            from tinycua.config.types import ValidationResult

            try:
                self.agent_monitor.on_after_node_call(
                    node.node_id,
                    self.root_session.session_id,
                    1,  # attempt 1 at agent level
                    llm_result,
                    # Validation is node-internal; loop doesn't run validate_output().
                    # Use NodeMonitor for per-attempt validation results.
                    ValidationResult(is_valid=True, errors=[]),
                )
            except Exception:
                logger.debug(
                    "node=%s agent_monitor_after_hook_exception",
                    node.node_id,
                    exc_info=True,
                )

        # Build the response object for on_complete: DecisionNode expects
        # a DecisionResult with a route_label; pass a synthetic one so
        # on_complete routing (QueryAnalyst._route_worker) works correctly.
        on_complete_response: LLMResult | DecisionResult = llm_result
        if isinstance(node, DecisionNode):
            # DecisionNode subclass — build a synthetic DecisionResult
            # with the raw content as route_label for on_complete routing.
            on_complete_response = DecisionResult(
                route_label=content,
                analysis_response=llm_result,
                classification_response=llm_result,
            )
        node.on_complete(self.queue, on_complete_response)

        # Propagate context on node termination (ISSUE-601): use the
        # propagation engine instead of legacy _transfer_session_context().
        rule = node.config.propagation or PropagationRule()
        parent_session = self._find_parent_session(node)
        propagate_on_termination(
            node.session or self.root_session,
            parent_session,
            self.root_session,
            rule,
        )

        return content, response.get("tool_calls") or []

    def _find_parent_session(self, node: Node) -> Session | None:
        """Find the parent session for a node by looking at queue position.

        In the flat loop architecture, all nodes share root_session.
        Returns None (no separate parent) since propagate_on_termination()
        handles propagation to root_session directly.

        Args:
            node: The node to find the parent session for.

        Returns:
            None in the flat loop architecture.
        """
        return None

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
            dedupe = node.config.message_policy.dedupe_by_origin_record_id
            if dedupe:
                messages.extend(
                    build_messages_with_dedupe(
                        self.root_session, dedupe_by_origin_record_id=True
                    )
                )
            else:
                for m in self.root_session.session_context:
                    if isinstance(m, dict):
                        messages.append(
                            {
                                "role": m.get("role", "user"),
                                "content": str(m.get("content", "")),
                            }
                        )
                    else:
                        messages.append(
                            {
                                "role": "user",
                                "content": str(m.content),
                            }
                        )

        # Add chat history if policy says so
        if (
            node.config.message_policy.include_chat_history
            and self.root_session.chat_history
        ):
            messages.extend(
                {
                    "role": m.role,
                    "content": str(m.content),
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
