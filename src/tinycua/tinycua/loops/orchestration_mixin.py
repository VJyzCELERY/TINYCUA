"""Orchestration and streaming mixin for TinyCUALoop."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops.context_rendering import sanitize_internal_reprs
from tinycua.loops.node import NodeRunContext
from tinycua.loops.propagation import PropagationRule, finalize_terminal_output, propagate_on_termination
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.models.node_handoff import NodeHandoff

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class OrchestrationMixin:
    """Orchestration and streaming mixin for TinyCUALoop."""

    def _node_run_context(
        self,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None,
        stream_messages: list[dict[str, Any]] | None = None,
    ) -> NodeRunContext:
        """Create injected runtime services for node-owned run entrypoints."""

        async def sync_executor(
            node: Node,
            node_input: NodeInputLike,
        ) -> tuple[str, list[dict[str, Any]]]:
            return await self._execute_node(
                node,
                agent,
                tools,
                override_instructions,
                node_input,
            )

        async def stream_executor(
            node: Node,
            node_input: NodeInputLike,
        ) -> AsyncIterator[dict[str, Any]]:
            async for event in self._stream_node_events(
                node,
                agent,
                tools,
                override_instructions,
                node_input,
                stream_messages,
            ):
                yield event

        return NodeRunContext(
            sync_executor=sync_executor,
            stream_executor=stream_executor,
        )

    def _maybe_populate_root_mission(self, node: Node) -> None:
        """Populate the canonical mission on the root task after TaskCreate.

        Derives ``mission`` (original request) and ``inherited_constraints``
        from the most recent ``DigestedInformation`` in the root session
        context, or from the raw user query when no digest exists. Idempotent:
        an existing mission is never overwritten. See FR-001.

        Args:
            node: The node that just completed; only ``task_create`` triggers
                population.
        """
        if node.node_id != "task_create":
            return
        store = self.root_session.task_store
        if store.root_task_id is None or store.root_task_id not in store.tasks:
            return
        root = store.tasks[store.root_task_id]
        if root.metadata.get("mission"):
            return  # idempotent: do not clobber an existing mission.
        from tinycua.models.digested_information import DigestedInformation

        digest: DigestedInformation | None = None
        for entry in reversed(self.root_session.session_context):
            content = getattr(entry, "content", None)
            if isinstance(content, DigestedInformation):
                digest = content
                break
        if digest is not None:
            root.metadata["mission"] = digest.original_query or ""
            root.metadata["inherited_constraints"] = list(digest.constraints)
            # Carry the digester's comprehensive research into the mission
            # so downstream nodes (Analyzer, Executor, Reviewer) see the
            # first-layer exploration findings as context, not just the
            # bare original query. Rendered by _render_mission_block as the
            # structured {context}\n{query} mission prefix.
            root.metadata["mission_context"] = digest.context_summary or ""
            root.metadata["mission_key_points"] = list(digest.key_points)
        else:
            root.metadata["mission"] = self._latest_user_text().strip()
            root.metadata["inherited_constraints"] = []
            root.metadata["mission_context"] = ""
            root.metadata["mission_key_points"] = []

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
        route_refresher = getattr(node, "refresh_route_options", None)
        if callable(route_refresher):
            route_refresher()
        resolved_tools = node.config.tool_policy.resolve_tools(tools)
        self._bind_session_tools(resolved_tools, node)
        self._resolved_tools_for_prompt = resolved_tools
        try:
            messages = self._build_node_messages(node, override_instructions)
        finally:
            self._resolved_tools_for_prompt = None
        return messages, resolved_tools

    async def _execute_deterministic_node(
        self,
        node: Node,
        resolved_tools: list[Tool],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Execute a deterministic runtime node without an LLM call."""
        runner = getattr(node, "run_deterministic")
        llm_result = runner(self.queue)
        content = llm_result.content
        if content:
            self._record_node_content_transcript(node, content)
        self._apply_task_lifecycle_marker(node, content)

        on_complete_response = self._build_on_complete_response(node, llm_result)
        trace_entry = self._trace_entry(
            node,
            1,
            resolved_tools,
            on_complete_response,
            llm_result,
        )
        trace_entry["deterministic"] = True
        self._execution_trace.append(trace_entry)

        rule = node.config.propagation or PropagationRule()
        parent_session = self._find_parent_session(node)
        await propagate_on_termination(
            node.session or self.root_session,
            parent_session,
            self.root_session,
            rule,
        )
        return content, llm_result.tool_calls

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

        # Milestone 8 Stream B: cross-node compaction trigger. Compact
        # session_context before building messages when the previous call
        # (in any prior node) neared the context window. Runs before
        # _prepare_node so the compacted session_context is what the
        # continuation renderers see.
        await self._maybe_compact(node, agent)

        messages, resolved_tools = self._prepare_node(
            node,
            tools,
            override_instructions,
        )
        self._record_node_call_transcript(node, messages, resolved_tools)

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

        deterministic_runner = getattr(node, "run_deterministic", None)
        if callable(deterministic_runner):
            return await self._execute_deterministic_node(node, resolved_tools)

        llm_result, attempt, validation = await self._call_node_with_retry(
            node,
            agent,
            messages,
            resolved_tools,
        )
        content = llm_result.content
        result_metadata = dict(llm_result.metadata)
        if not validation.is_valid:
            if self._recover_task_analyzer_validation_failure(node, validation):
                on_complete_response = self._build_on_complete_response(node, llm_result)
                trace_entry = self._trace_entry(
                    node,
                    attempt,
                    resolved_tools,
                    on_complete_response,
                    llm_result,
                )
                trace_entry["validation_errors"] = list(validation.errors)
                self._execution_trace.append(trace_entry)
                return content, llm_result.tool_calls
            if self._recover_task_executor_validation_failure(
                node,
                validation,
                llm_result,
            ):
                on_complete_response = self._build_on_complete_response(node, llm_result)
                trace_entry = self._trace_entry(
                    node,
                    attempt,
                    resolved_tools,
                    on_complete_response,
                    llm_result,
                )
                trace_entry["validation_errors"] = list(validation.errors)
                self._execution_trace.append(trace_entry)
                return content, llm_result.tool_calls
            # Unbounded tightened-retry loop — never exits until validation
            # passes. No graceful continue, no exit-0 escape hatch.
            recovered_result, _ = await self._unbounded_recovery(
                node, agent, resolved_tools, llm_result, validation
            )
            trace_entry = self._trace_entry(
                node,
                attempt,
                resolved_tools,
                recovered_result.content,
                recovered_result,
            )
            trace_entry["validation_errors"] = []
            trace_entry["recovery"] = "unbounded_recovery"
            self._execution_trace.append(trace_entry)
            llm_result = self._record_node_output(
                node, recovered_result.content, recovered_result.tool_calls
            )
            llm_result.metadata.update(dict(recovered_result.metadata))
            if recovered_result.content:
                self._record_node_content_transcript(node, recovered_result.content)
            return recovered_result.content, recovered_result.tool_calls
        llm_result = self._record_node_output(node, content, llm_result.tool_calls)
        llm_result.metadata.update(result_metadata)
        if content:
            self._record_node_content_transcript(node, content)
        self._record_tool_result_transcripts(
            node,
            llm_result.metadata.get("tool_results", []),
        )
        self._apply_loop_result_hook(node, llm_result, node_input)
        self._publish_structured_outputs_to_root(node)
        self._maybe_populate_root_mission(node)
        self._maybe_warn_reviewer_no_verification(node, llm_result)
        self._apply_task_lifecycle_marker(node, content)

        # Fire agent_monitor after-hook (if configured)
        if self.agent_monitor is not None:
            try:
                self.agent_monitor.on_after_node_call(
                    node.node_id,
                    self.root_session.session_id,
                    attempt,
                    llm_result,
                    validation,
                )
            except Exception:
                logger.debug(
                    "node=%s agent_monitor_after_hook_exception",
                    node.node_id,
                    exc_info=True,
                )

        on_complete_response = self._build_on_complete_response(node, llm_result)
        node.on_complete(self.queue, on_complete_response)

        trace_entry = self._trace_entry(
            node,
            attempt,
            resolved_tools,
            on_complete_response,
            llm_result,
        )
        self._execution_trace.append(trace_entry)

        # Propagate context on node termination (ISSUE-601): use the
        # propagation engine instead of legacy _transfer_session_context().
        rule = node.config.propagation or PropagationRule()
        parent_session = self._find_parent_session(node)
        await propagate_on_termination(
            node.session or self.root_session,
            parent_session,
            self.root_session,
            rule,
        )

        return content, llm_result.tool_calls

    async def _finalize_streamed_node(
        self,
        node: Node,
        agent: Agent,
        content_parts: list[str],
        collected_tool_calls: list[dict[str, Any]],
        resolved_tools: list[Tool],
        node_input: NodeInputLike | None = None,
        *,
        attempt: int = 1,
        retry_tool_results: list[dict[str, Any]] | None = None,
    ) -> tuple[str, ValidationResult, LLMResult]:
        """Finalize a streamed node: record output, fire lifecycle hooks.

        Args:
            node: The node that was streamed.
            agent: The SDK agent used for tool execution.
            content_parts: Accumulated text delta parts.
            collected_tool_calls: Collected tool call events.
            resolved_tools: Tools allowed for the streamed node.
            node_input: Direct input passed to the streamed node.
            attempt: Current retry attempt number for trace metadata.
            retry_tool_results: Latest prior retry tool results to preserve for
                validation of multi-step retry flows.

        Returns:
            The combined content, validation result, and LLMResult.
        """
        combined = "".join(content_parts)
        combined = sanitize_internal_reprs(combined)
        llm_result = LLMResult(
            content=combined,
            role="assistant",
            tool_calls=collected_tool_calls,
        )
        self._coerce_structured_tool_calls(llm_result, resolved_tools)
        self._coerce_terminate_only_response(resolved_tools, llm_result)
        collected_tool_calls = llm_result.tool_calls
        tool_results = await self._execute_tool_calls(
            agent,
            collected_tool_calls,
            resolved_tools,
        )
        if tool_results:
            llm_result.metadata["tool_results"] = tool_results
            self._prepend_retry_tool_results(llm_result, retry_tool_results or [])
            self._enrich_task_results_from_tool_batch(
                node,
                llm_result.metadata["tool_results"],
            )
            self._record_tool_result_transcripts(node, tool_results)
            self._fill_content_from_recorded_task_result(llm_result)
        elif retry_tool_results:
            self._prepend_retry_tool_results(llm_result, retry_tool_results)
        combined = llm_result.content
        validation = self._validate_node_result(node, llm_result)
        if not validation.is_valid:
            on_complete_response = self._build_on_complete_response(node, llm_result)
            trace_entry = self._trace_entry(
                node,
                attempt,
                resolved_tools,
                on_complete_response,
                llm_result,
            )
            trace_entry["validation_errors"] = list(validation.errors)
            self._execution_trace.append(trace_entry)
            return combined, validation, llm_result

        # Record valid output as reusable node context only after validation passes
        result_metadata = dict(llm_result.metadata)
        llm_result = self._record_node_output(node, combined, llm_result.tool_calls)
        llm_result.metadata.update(result_metadata)

        self._apply_loop_result_hook(node, llm_result, node_input)
        self._publish_structured_outputs_to_root(node)
        self._maybe_populate_root_mission(node)
        self._maybe_warn_reviewer_no_verification(node, llm_result)
        self._apply_task_lifecycle_marker(node, combined)
        on_complete_response = self._build_on_complete_response(node, llm_result)
        node.on_complete(self.queue, on_complete_response)

        trace_entry = self._trace_entry(
            node,
            attempt,
            resolved_tools,
            on_complete_response,
            llm_result,
        )
        self._execution_trace.append(trace_entry)

        # Propagate context on node termination
        rule = node.config.propagation or PropagationRule()
        parent_session = self._find_parent_session(node)
        await propagate_on_termination(
            node.session or self.root_session,
            parent_session,
            self.root_session,
            rule,
        )

        return combined, validation, llm_result

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
        node_context = self._node_run_context(
            agent,
            tools,
            override_instructions,
            all_messages,
        )
        self._usage_events = []
        try:
            while not self.queue.is_empty():
                node = self.queue.current
                if node is None:
                    break
                async for event in node.stream(
                    node_context,
                    self.queue.input_for_current(),
                ):
                    yield event

                # Stop at terminal nodes — do not advance past them
                if node.is_terminal and self.queue.current is node:
                    finalize_terminal_output(
                        node.session or self.root_session,
                        self.root_session,
                    )
                    break
                if node.is_terminal:
                    continue

                self.queue.advance(self._pop_handoff_for_next(node))
        finally:
            self._working_messages = all_messages

    def _pop_handoff_for_next(self, node: Node) -> NodeHandoff | None:
        """Return an explicit handoff from the completed node to the next node."""
        next_node = self.queue.items[1] if len(self.queue.items) > 1 else None
        if next_node is None:
            return None
        for index, handoff in enumerate(self._pending_handoffs):
            if handoff.source_node != node.node_id:
                continue
            if handoff.target_node not in (None, next_node.node_id):
                continue
            return self._pending_handoffs.pop(index)
        return self._implicit_structured_handoff(node, next_node.node_id)

    def _implicit_structured_handoff(
        self,
        node: Node,
        target_node_id: str,
    ) -> NodeHandoff | None:
        """Create narrow typed handoffs for existing structured node outputs."""
        from tinycua.models.digested_information import DigestedInformation

        if node.session is None:
            return None
        if node.node_id not in {"digester", "result_aggregation"}:
            return None
        for entry in reversed(node.session.session_context):
            content = getattr(entry, "content", None)
            if isinstance(content, DigestedInformation):
                return NodeHandoff(
                    source_node=node.node_id,
                    target_node=target_node_id,
                    instruction="Use the digested information as scoped input.",
                    payload={"digested_information": content},
                )
            if node.node_id == "result_aggregation" and content:
                return NodeHandoff(
                    source_node=node.node_id,
                    target_node=target_node_id,
                    instruction="Use the aggregation result to answer the user.",
                    payload={"aggregation": content},
                )
        return None

    async def _stream_node_events(
        self,
        node: Node,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None,
        node_input: NodeInputLike,
        stream_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream one node through its lifecycle and runtime services."""
        if isinstance(node, TinyCUAQueryAnalystNode):
            node._queue = self.queue
        messages, resolved_tools = self._prepare_node(
            node,
            tools,
            override_instructions,
        )
        self._record_node_call_transcript(node, messages, resolved_tools)
        if stream_messages is not None:
            stream_messages.extend(messages)

        policy = node.config.stream_policy
        emit_lifecycle = policy.emit_internal_events
        include_meta = policy.include_node_metadata
        final_only = policy.final_response_only
        node_type = type(node).__name__
        attempt = 1

        async for event in self._stream_node_start(node, node_type, attempt):
            yield self._enrich_and_yield(
                event,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )

        deterministic_runner = getattr(node, "run_deterministic", None)
        if callable(deterministic_runner):
            async for event in self._stream_deterministic_node_events(
                node,
                resolved_tools,
                stream_messages,
                emit_lifecycle,
                include_meta,
                final_only,
                node_type,
                attempt,
            ):
                yield event
            return

        async for event in self._stream_llm_node_events(
            node,
            agent,
            messages,
            resolved_tools,
            node_input,
            stream_messages,
            emit_lifecycle,
            include_meta,
            final_only,
            node_type,
            attempt,
        ):
            yield event

    async def _stream_nonterminal_sync_node_events(
        self,
        node: Node,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None,
        node_input: NodeInputLike,
        stream_messages: list[dict[str, Any]] | None,
        emit_lifecycle: bool,
        include_meta: bool,
        final_only: bool,
        node_type: str,
        attempt: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute nonterminal stream nodes through sync parity path."""
        try:
            combined, tool_calls = await self._execute_node(
                node,
                agent,
                tools,
                override_instructions,
                node_input,
            )
        except Exception:
            error_event = self._make_error_event(node.node_id, node_type, attempt)
            yield self._enrich_and_yield(
                error_event,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )
            raise
        if stream_messages is not None:
            if combined:
                stream_messages.append({"role": "assistant", "content": combined})
            for tool_call in tool_calls:
                stream_messages.append({"role": "assistant", "tool_calls": [tool_call]})
        completed = self._emit_lifecycle_event(
            "node.completed",
            node.node_id,
            node_type,
            attempt,
            emit_lifecycle,
            final_only,
            False,
            content=combined,
            finish_reason="completed" if combined else "empty",
        )
        if completed is not None:
            yield self._enrich_and_yield(
                completed,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )

    async def _stream_node_start(
        self,
        node: Node,
        node_type: str,
        attempt: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Emit a node.started lifecycle event if policy allows it."""
        policy = node.config.stream_policy
        started = self._emit_lifecycle_event(
            "node.started",
            node.node_id,
            node_type,
            attempt,
            policy.emit_internal_events,
            policy.final_response_only,
            node.is_terminal,
        )
        if started is not None:
            yield started

    async def _stream_deterministic_node_events(
        self,
        node: Node,
        resolved_tools: list[Tool],
        stream_messages: list[dict[str, Any]] | None,
        emit_lifecycle: bool,
        include_meta: bool,
        final_only: bool,
        node_type: str,
        attempt: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run a deterministic node and emit completion lifecycle events."""
        combined, tool_calls = await self._execute_deterministic_node(node, resolved_tools)
        if stream_messages is not None:
            for tool_call in tool_calls:
                stream_messages.append({"role": "assistant", "tool_calls": [tool_call]})
        completed = self._emit_lifecycle_event(
            "node.completed",
            node.node_id,
            node_type,
            attempt,
            emit_lifecycle,
            final_only,
            node.is_terminal,
            content=combined,
            finish_reason="completed",
        )
        if completed is not None:
            yield self._enrich_and_yield(
                completed,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )

    async def _stream_llm_node_events(
        self,
        node: Node,
        agent: Agent,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
        node_input: NodeInputLike,
        stream_messages: list[dict[str, Any]] | None,
        emit_lifecycle: bool,
        include_meta: bool,
        final_only: bool,
        node_type: str,
        attempt: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream an LLM-backed node and finalize its output."""
        max_attempts = self._effective_max_attempts(node)
        last_validation = ValidationResult(is_valid=True, errors=[])
        last_result = LLMResult()
        last_combined = ""
        base_messages = [dict(message) for message in messages]
        retry_message: str | None = None
        retry_feedback: list[dict[str, Any]] = []
        retry_tool_results: list[dict[str, Any]] = []
        for attempt_number in range(attempt, max_attempts + 1):
            attempt_messages = self._messages_with_retry_prompt(
                base_messages,
                retry_feedback,
                retry_message,
            )
            attempt_tools = self._tools_for_retry_attempt(
                node,
                resolved_tools,
                retry_message,
            )
            llm_call = self._emit_lifecycle_event(
                "node.llm_call",
                node.node_id,
                node_type,
                attempt_number,
                emit_lifecycle,
                final_only,
                node.is_terminal,
            )
            if llm_call is not None:
                yield self._enrich_and_yield(
                    llm_call,
                    include_meta,
                    node.node_id,
                    node_type,
                    attempt_number,
                )
            content_parts: list[str] = []
            collected_tool_calls: list[dict[str, Any]] = []
            try:
                async for event in self._collect_stream_events(
                    node,
                    agent,
                    attempt_messages,
                    attempt_tools,
                    content_parts,
                    collected_tool_calls,
                    include_meta,
                    final_only,
                    node_type,
                    attempt_number,
                ):
                    yield event
            except Exception:
                error_event = self._make_error_event(
                    node.node_id,
                    node_type,
                    attempt_number,
                )
                yield self._enrich_and_yield(
                    error_event,
                    include_meta,
                    node.node_id,
                    node_type,
                    attempt_number,
                )
                raise

            combined, validation, llm_result = await self._finalize_streamed_node(
                node,
                agent,
                content_parts,
                collected_tool_calls,
                attempt_tools,
                node_input,
                attempt=attempt_number,
                retry_tool_results=retry_tool_results,
            )
            last_combined = combined
            last_validation = validation
            last_result = llm_result
            if validation.is_valid:
                if combined and not node.is_terminal:
                    self._record_node_content_transcript(node, combined)
                if combined and node.is_terminal:
                    async for event in self._stream_terminal_text(
                        combined,
                        include_meta,
                        node.node_id,
                        node_type,
                        attempt_number,
                        final_only,
                    ):
                        yield event
                if stream_messages is not None:
                    if combined:
                        stream_messages.append({"role": "assistant", "content": combined})
                    for tool_call in collected_tool_calls:
                        stream_messages.append(
                            {"role": "assistant", "tool_calls": [tool_call]}
                        )
                async for event in self._stream_node_completed(
                    node,
                    combined,
                    emit_lifecycle,
                    include_meta,
                    final_only,
                    node_type,
                    attempt_number,
                ):
                    yield event
                return
            if attempt_number < max_attempts:
                error = ValidationError("; ".join(validation.errors))
                retry_message = self._stream_retry_message(
                    agent,
                    node,
                    resolved_tools,
                    error,
                    attempt_number,
                    llm_result,
                )
                retry_feedback = self._tool_feedback_messages(llm_result)
                retry_tool_results = self._tool_results_from_llm_result(llm_result)
                self._record_retry_continuation(node, retry_message, attempt_number)

        async for event in self._stream_exhausted_node_events(
            node,
            agent,
            resolved_tools,
            last_combined,
            last_validation,
            last_result,
            emit_lifecycle,
            include_meta,
            final_only,
            node_type,
            max_attempts,
        ):
            yield event

    # Prerequisite chains: the ordered sequence of tools each node must call
    # before it can terminate. Recovery tracks which have been called and only
    # asks for the missing ones in order. ``terminate`` is always last.
    _RECOVERY_CHAINS: dict[str, tuple[str, ...]] = {
        "result_reviewer": ("task_review_decision", "task_inspect", "terminate"),
        "task_executor": ("task_result_update", "terminate"),
        "task_create": ("task_init", "terminate"),
        "task_analyzer": ("task_decompose", "terminate"),
        "task_assessor": ("node_handoff", "terminate"),
    }

    def _resolve_recovery_tool(
        self,
        node: Node,
        tool_name: str,
        resolved_tools: list[Tool],
    ) -> Tool | None:
        """Resolve a Tool object by name — from scope or constructed on demand.

        ``terminate`` is a universal lifecycle tool not in any node's static
        scope. It is constructed on demand. Other tools are found in the
        node's resolved tools or its tool policy scope.
        """
        if tool_name == "terminate":
            from tinycua.tools.task_tools import TerminateTool
            return TerminateTool()
        # Check resolved_tools first (passed from the caller).
        for tool in resolved_tools:
            if getattr(tool, "name", "") == tool_name:
                return tool
        # Fall back to the node's tool policy scope.
        resolved = getattr(node.config, "tool_policy", None)
        if resolved is not None:
            tools = resolved.resolve_tools([])
            for tool in tools:
                if getattr(tool, "name", "") == tool_name:
                    return tool
        return None

    def _log_recovery_cycle(
        self,
        node: Node,
        validation: ValidationResult,
        cycle: int,
        stage_results: dict[str, bool],
    ) -> None:
        """Log system state on every recovery cycle for traceability.

        Emits a structured log record showing the node, validation errors, task
        store state, queue contents, and which recovery stages failed. This
        makes stuck loops visible in logs without decoding stdout.
        """
        store = self.root_session.task_store
        total = len(store.tasks)
        completed = sum(1 for t in store.tasks.values() if t.status.value == "completed")
        pending = sum(1 for t in store.tasks.values() if t.status.value == "pending")
        in_progress = sum(1 for t in store.tasks.values() if t.status.value == "in_progress")
        active_id = store.active_task_id or "none"
        root_id = store.root_task_id or "none"
        queue_ids = [n.node_id for n in self.queue.items]
        errors = "; ".join(validation.errors) or "unknown"
        stages = ", ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in stage_results.items())
        logger.warning(
            "node=%s stuck — recovery cycle=%d errors=%s "
            "task_store root=%s active=%s completed=%d/%d pending=%d in_progress=%d "
            "stages=[%s] queue=%s retrying with tightened context",
            node.node_id,
            cycle,
            errors,
            root_id,
            active_id,
            completed,
            total,
            pending,
            in_progress,
            stages,
            queue_ids,
        )

    async def _unbounded_recovery(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
        validation: ValidationResult,
    ) -> tuple[LLMResult, ValidationResult]:
        """Unbounded 2-track recovery — never exits until validation passes.

        Milestone 3 redesign: replaces the 5-stage forcing escalation with a
        2-track system:

        1. **Deterministic track**: if the only missing prerequisite is
           ``terminate`` (a no-arg tool), call it directly without an LLM
           round-trip. This is not stealing an LLM decision — terminate takes
           no parameters (FR-011).

        2. **Structured-output track**: the LLM is called with
           ``response_format: json_schema`` built from the missing tool's
           parameters, constraining it to produce valid JSON. The LLM stays
           the decider — the runtime never synthesizes the call (unlike the
           removed ``_judge_retry`` stage). If the output is invalid, the
           loop retries with the schema error (unbounded).

        FR-015: after 10 consecutive structured-output failures, a stuck-model
        diagnostic is logged (observability only — the loop continues to
        preserve the zero-exit, one-shot, no-HITL guarantee).

        No graceful exit — the loop only returns when validation passes.
        """
        cycle = 0
        current_result = llm_result
        current_validation = validation
        # Accumulate successful tool results (dicts) across the entire recovery.
        # Keyed by tool name — last successful result wins. This lets the
        # validator see the full accumulated state even when a stage only
        # produced one tool call.
        accumulated_results: dict[str, dict[str, Any]] = {}
        # Seed with successful tools from the original failed result.
        for item in llm_result.metadata.get("tool_results", []):
            if (
                isinstance(item, dict)
                and isinstance(item.get("output"), dict)
                and item["output"].get("success") is True
            ):
                accumulated_results[str(item.get("name"))] = item
        # Track consecutive structured-output failures for the stuck-model
        # diagnostic (FR-015). The loop is still unbounded — this is for
        # observability only, not a bound.
        consecutive_schema_failures = 0
        while not current_validation.is_valid:
            cycle += 1
            stage_results: dict[str, bool] = {}
            accumulated_successful = set(accumulated_results.keys())
            # Determine which prerequisite tools are still missing.
            missing = self._missing_recovery_tools_from_set(
                node, accumulated_successful
            )
            # Deterministic track: if the ONLY missing prerequisite is
            # terminate, call it directly without an LLM round-trip. terminate
            # has no meaningful parameters — there is nothing for the model to
            # decide. This is not stealing an LLM decision (FR-011).
            if missing == ["terminate"]:
                terminated = await self._direct_terminate(node, agent)
                if terminated is not None:
                    current_result, current_validation = terminated
                    self._accumulate_results(current_result, accumulated_results)
                    current_validation = self._revalidate_with_accumulated(
                        node, current_result, accumulated_results
                    )
                    if current_validation.is_valid:
                        return current_result, current_validation
                stage_results["direct_terminate"] = terminated is not None
            # Structured-output track (Milestone 3): the LLM is constrained via
            # response_format: json_schema to produce valid tool-call JSON.
            # The LLM stays the decider — the runtime never synthesizes the
            # call (unlike the removed _judge_retry stage). Replaces the
            # 3-stage escalation (focused → tightening → judge).
            recovery = await self._structured_output_retry(
                node, agent, resolved_tools, current_result, current_validation,
                missing_tools=missing,
            )
            stage_results["structured_output_retry"] = recovery is not None
            if recovery is not None:
                current_result, current_validation = recovery
                self._accumulate_results(current_result, accumulated_results)
                current_validation = self._revalidate_with_accumulated(
                    node, current_result, accumulated_results
                )
                if current_validation.is_valid:
                    return current_result, current_validation
                consecutive_schema_failures = 0
            else:
                # Fallback: focused retry (expose missing tools, no response_format).
                # This handles LLMs that don't support json_schema and mock LLMs
                # in tests. The LLM freely decides the arguments via normal
                # tool calls — still LLM-decided, just not schema-constrained.
                focused = await self._recovery_retry(
                    node, agent, resolved_tools, current_result, current_validation,
                    missing_tools=missing,
                )
                stage_results["focused_retry"] = focused is not None
                if focused is not None:
                    current_result, current_validation = focused
                    self._accumulate_results(current_result, accumulated_results)
                    current_validation = self._revalidate_with_accumulated(
                        node, current_result, accumulated_results
                    )
                    if current_validation.is_valid:
                        return current_result, current_validation
                    consecutive_schema_failures = 0
                else:
                    consecutive_schema_failures += 1
                # FR-015: stuck-model diagnostic (observability, not a bound).
                if consecutive_schema_failures >= 10:
                    logger.warning(
                        "node=%s stuck-model — %d consecutive structured-output "
                        "failures. The loop continues (zero-exit guarantee) but "
                        "this model may be unable to produce the required output.",
                        node.node_id,
                        consecutive_schema_failures,
                    )
                    consecutive_schema_failures = 0  # reset to avoid log spam
            # All stages failed — log state and loop back.
            self._log_recovery_cycle(node, current_validation, cycle, stage_results)

    async def _direct_terminate(
        self,
        node: Node,
        agent: Agent,
    ) -> tuple[LLMResult, ValidationResult] | None:
        """Call terminate directly without an LLM round-trip.

        ``terminate`` has no meaningful parameters — there is nothing for the
        model to decide. During recovery, if terminate is the only missing
        prerequisite, we call it directly. This builds a synthetic tool call,
        executes it via the normal tool executor, and returns the result.

        Returns (result, validation) if the terminate call succeeds, else None.
        """
        from tinycua.tools.task_tools import TerminateTool

        terminate_tool = TerminateTool()
        terminate_call: dict[str, Any] = {
            "id": "call_direct_terminate",
            "type": "function",
            "function": {
                "name": "terminate",
                "arguments": "{}",
            },
        }
        try:
            tool_results = await self._execute_tool_calls(
                agent, [terminate_call], [terminate_tool]
            )
        except Exception:
            logger.debug("node=%s direct_terminate failed", node.node_id, exc_info=True)
            return None
        result = LLMResult(
            content="[Direct terminate — no LLM call needed]",
            role="assistant",
            tool_calls=[terminate_call],
            metadata={"tool_results": tool_results},
        )
        self._record_node_content_transcript(
            node,
            "Direct terminate: terminate called without LLM (no parameters to decide).",
        )
        return result, self._validate_node_result(node, result)

    @staticmethod
    def _accumulate_results(
        llm_result: LLMResult,
        accumulated: dict[str, dict[str, Any]],
    ) -> None:
        """Add successful tool results from a result to the accumulated dict."""
        for item in llm_result.metadata.get("tool_results", []):
            if (
                isinstance(item, dict)
                and isinstance(item.get("output"), dict)
                and item["output"].get("success") is True
            ):
                accumulated[str(item.get("name"))] = item

    def _revalidate_with_accumulated(
        self,
        node: Node,
        llm_result: LLMResult,
        accumulated: dict[str, dict[str, Any]],
    ) -> ValidationResult:
        """Re-validate with accumulated tool results merged into the result.

        The recovery stages produce results with only the latest tool calls.
        But the validator checks for ALL required tools in a single result.
        This merges accumulated prior tool results into the result's
        metadata before validating, so the validator sees the full state.
        """
        existing = llm_result.metadata.get("tool_results", [])
        existing_names = {
            str(item.get("name"))
            for item in existing
            if isinstance(item, dict)
        }
        merged = list(existing)
        for name, item in accumulated.items():
            if name not in existing_names:
                merged.append(item)
        if len(merged) != len(existing):
            llm_result.metadata = dict(llm_result.metadata)
            llm_result.metadata["tool_results"] = merged
        return self._validate_node_result(node, llm_result)

    def _missing_recovery_tools_from_set(
        self,
        node: Node,
        accumulated_successful: set[str],
    ) -> list[str]:
        """Return prerequisite tools not yet called, using the accumulated set."""
        chain = self._RECOVERY_CHAINS.get(node.node_id, ())
        if not chain:
            return []
        return [name for name in chain if name not in accumulated_successful]

    async def _stream_exhausted_node_events(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        combined: str,
        validation: ValidationResult,
        llm_result: LLMResult,
        emit_lifecycle: bool,
        include_meta: bool,
        final_only: bool,
        node_type: str,
        max_attempts: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle streamed retry exhaustion without terminal synthesis."""
        if self._should_fallback_terminal_response(node, validation):
            fallback = self._response_fallback_content()
            async for event in self._stream_terminal_text(
                fallback,
                include_meta,
                node.node_id,
                node_type,
                max_attempts,
                final_only,
            ):
                yield event
            async for event in self._stream_node_completed(
                node,
                fallback,
                emit_lifecycle,
                include_meta,
                final_only,
                node_type,
                max_attempts,
            ):
                yield event
            return
        node._handle_exhaustion(validation, max_attempts)
        if self._recover_task_assessor_validation_failure(node, validation):
            completed = self._emit_lifecycle_event(
                "node.completed",
                node.node_id,
                node_type,
                max_attempts,
                emit_lifecycle,
                final_only,
                node.is_terminal,
                content=combined,
                finish_reason="completed",
            )
            if completed is not None:
                yield self._enrich_and_yield(
                    completed,
                    include_meta,
                    node.node_id,
                    node_type,
                    max_attempts,
                )
            return
        if self._recover_task_analyzer_validation_failure(node, validation):
            completed = self._emit_lifecycle_event(
                "node.completed",
                node.node_id,
                node_type,
                max_attempts,
                emit_lifecycle,
                final_only,
                node.is_terminal,
                content=combined,
                finish_reason="completed",
            )
            if completed is not None:
                yield self._enrich_and_yield(
                    completed,
                    include_meta,
                    node.node_id,
                    node_type,
                    max_attempts,
                )
            return
        if self._recover_task_executor_validation_failure(node, validation, llm_result):
            completed = self._emit_lifecycle_event(
                "node.completed",
                node.node_id,
                node_type,
                max_attempts,
                emit_lifecycle,
                final_only,
                node.is_terminal,
                content=combined,
                finish_reason="completed",
            )
            if completed is not None:
                yield self._enrich_and_yield(
                    completed,
                    include_meta,
                    node.node_id,
                    node_type,
                    max_attempts,
                )
            return
        # Unbounded tightened-retry loop — never exits until validation
        # passes. Cycles through focused → tightening → judge stages,
        # logging state to stderr each cycle. No graceful continue, no
        # exit-0 escape hatch. The node must produce valid output before
        # the queue can advance past it (queue integrity invariant).
        recovered_result, _ = await self._unbounded_recovery(
            node, agent, resolved_tools, llm_result, validation
        )
        recovery_content = recovered_result.content or combined
        # Record the recovered output and fire on_complete so the queue
        # gets the next nodes (schedule_after_review / schedule_next).
        self._record_node_output(node, recovery_content, recovered_result.tool_calls)
        recovered_result.metadata = dict(recovered_result.metadata)
        if recovery_content:
            self._record_node_content_transcript(node, recovery_content)
        self._record_tool_result_transcripts(
            node,
            recovered_result.metadata.get("tool_results", []),
        )
        self._apply_loop_result_hook(node, recovered_result, None)
        self._publish_structured_outputs_to_root(node)
        self._maybe_populate_root_mission(node)
        self._maybe_warn_reviewer_no_verification(node, recovered_result)
        self._apply_task_lifecycle_marker(node, recovery_content)
        on_complete_response = self._build_on_complete_response(node, recovered_result)
        node.on_complete(self.queue, on_complete_response)
        async for event in self._stream_node_completed(
            node,
            recovery_content,
            emit_lifecycle,
            include_meta,
            final_only,
            node_type,
            max_attempts,
        ):
            yield event
        return

    async def _stream_node_completed(
        self,
        node: Node,
        combined: str,
        emit_lifecycle: bool,
        include_meta: bool,
        final_only: bool,
        node_type: str,
        attempt: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Emit node.completed lifecycle after node finalization."""
        completed = self._emit_lifecycle_event(
            "node.completed",
            node.node_id,
            node_type,
            attempt,
            emit_lifecycle,
            final_only,
            node.is_terminal,
            content=combined,
            finish_reason="completed" if combined else "empty",
        )
        if completed is not None:
            yield self._enrich_and_yield(
                completed,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )
