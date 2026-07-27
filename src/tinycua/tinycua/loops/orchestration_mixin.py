"""Orchestration and streaming mixin for TinyCUALoop."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops.context_rendering import sanitize_internal_reprs
from tinycua.loops.node import NodeExecutionError, NodeRunContext
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.propagation import (
    PropagationRule,
    finalize_terminal_output,
    propagate_on_termination,
)
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.session_context_query import find_latest_entry
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.session_context_entry import entry_content

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike

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

        digest = find_latest_entry(self.root_session, DigestedInformation)
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
        self._resolved_tools_for_prompt = self._phase_tools(
            node, resolved_tools, node.progress.lifecycle_phase
        )
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

    async def _handle_validation_failure(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        llm_result: LLMResult,
        validation: ValidationResult,
        attempt: int,
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """Handle a validation failure via the 3-way recovery path.

        Returns (content, tool_calls) when a recovery path succeeds, or None
        when the caller should fall through to unbounded recovery.
        """
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
            return llm_result.content, llm_result.tool_calls
        if self._recover_task_executor_validation_failure(node, validation, llm_result):
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
            return llm_result.content, llm_result.tool_calls
        return None

    async def _finalize_node_success(
        self,
        node: Node,
        llm_result: LLMResult,
        validation: ValidationResult,
        attempt: int,
        node_input: NodeInputLike | None,
        resolved_tools: list[Tool],
        content: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Record output, fire hooks, on_complete, propagation. Returns (content, tool_calls)."""
        result_metadata = dict(llm_result.metadata)
        llm_result = self._record_node_output(node, content, llm_result.tool_calls)
        llm_result.metadata.update(result_metadata)
        if content:
            self._record_node_content_transcript(node, content)
        self._record_tool_result_transcripts(
            node,
            llm_result.metadata.get("tool_results", []),
            llm_result.tool_calls,
        )
        self._apply_loop_result_hook(node, llm_result, node_input)
        self._publish_structured_outputs_to_root(node)
        self._maybe_populate_root_mission(node)
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
        # Some routing nodes create structured audit entries in on_complete.
        # Publish again so those entries reach root retrieval context too.
        self._publish_structured_outputs_to_root(node)

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
        # FR-062: clean up node progress for completed nodes — don't store
        # done nodes. A re-enqueued node (reviewer sends back to executor)
        # gets a fresh NodeProgress on its next dispatch.
        self.root_session.node_progress.pop(node.node_id, None)
        return content, llm_result.tool_calls

    async def _execute_node(
        self,
        node: Node,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
        node_input: NodeInputLike | None = None,
        *,
        progress_prepared: bool = False,
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
            progress_prepared: Whether streaming re-entry already reset progress.

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

        try:
            llm_result, attempt, validation = await self._call_node_with_retry(
                node,
                agent,
                messages,
                resolved_tools,
                reset_progress=not progress_prepared,
            )
        except NodeExecutionError as exc:
            trace_entry = self._trace_entry(
                node,
                node.progress.attempt_count,
                resolved_tools,
                "",
                LLMResult(),
            )
            trace_entry["validation_errors"] = [str(exc)]
            self._execution_trace.append(trace_entry)
            raise
        content = llm_result.content
        if not validation.is_valid:
            recovered = await self._handle_validation_failure(
                node,
                agent,
                resolved_tools,
                llm_result,
                validation,
                attempt,
            )
            if recovered is not None:
                return recovered
            lazy_outcome = await self._maybe_lazy_pre_recovery(  # FR-087..093
                node, agent, resolved_tools, llm_result, validation
            )
            if lazy_outcome is not None:
                lazy_result, revalidated, is_valid = lazy_outcome
                if is_valid:
                    return await self._finalize_node_success(
                        node,
                        lazy_result,
                        revalidated,
                        attempt,
                        None,
                        resolved_tools,
                        lazy_result.content,
                    )
                llm_result, validation = lazy_result, revalidated
            try:
                recovery_result = await self._unbounded_recovery(
                    node, agent, resolved_tools, llm_result, validation
                )
            except NodeExecutionError:
                trace_entry = self._trace_entry(
                    node,
                    attempt,
                    resolved_tools,
                    self._build_on_complete_response(node, llm_result),
                    llm_result,
                )
                trace_entry["validation_errors"] = list(validation.errors)
                self._execution_trace.append(trace_entry)
                raise
            if recovery_result is None:
                # Re-entry: don't call on_complete, don't advance.
                # The caller (queue loop) re-dispatches this node fresh.
                self._record_node_content_transcript(
                    node,
                    "Recovery budget exhausted — re-entering node with fresh context.",
                )
                return "", []
            recovered_result, _ = recovery_result
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
        return await self._finalize_node_success(
            node,
            llm_result,
            validation,
            attempt,
            node_input,
            resolved_tools,
            content,
        )

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
            node,
        )
        if tool_results:
            llm_result.metadata["tool_results"] = tool_results
            self._track_tool_calls_in_progress(node, tool_results)
            self._prepend_retry_tool_results(llm_result, retry_tool_results or [])
            self._enrich_task_results_from_tool_batch(
                node,
                llm_result.metadata["tool_results"],
            )
            self._record_tool_result_transcripts(
                node, tool_results, collected_tool_calls
            )
            self._fill_content_from_recorded_task_result(llm_result)
        elif retry_tool_results:
            self._prepend_retry_tool_results(llm_result, retry_tool_results)
        combined = llm_result.content
        if node.contract.requires_terminate:
            if node.progress.lifecycle_phase == LifecyclePhase.ACTION:
                node.progress.advance_lifecycle(
                    LifecyclePhase.SUMMARY, combined.strip()
                )
                node.progress.advance_lifecycle(LifecyclePhase.COMMIT)
            else:
                self._advance_lifecycle_phase(node, llm_result)
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
        self._apply_task_lifecycle_marker(node, combined)
        on_complete_response = self._build_on_complete_response(node, llm_result)
        node.on_complete(self.queue, on_complete_response)
        self._publish_structured_outputs_to_root(node)

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
        # FR-062: clean up node progress for completed nodes.
        self.root_session.node_progress.pop(node.node_id, None)

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
                store = self.root_session.task_store
                if (
                    node.node_id == "task_executor"
                    and self._prepend_cancellation_review()
                ):
                    continue
                if (
                    node.node_id == "response"
                    and store.root_task_id is not None
                    and not store.all_done()
                ):
                    self.queue.items.pop(0)
                    from tinycua.loops.worker_runtime import WorkerRuntimeController

                    WorkerRuntimeController(
                        store, session=self.root_session
                    ).schedule_next(self.queue)
                    continue
                async for event in node.stream(
                    node_context,
                    self.queue.input_for_current(),
                ):
                    yield event

                # FR-060: check re-entry signal — if set, don't advance.
                # Re-dispatch the same node (still at items[0]) with fresh context.
                if self._recovery_reentry:
                    # _call_node_with_retry consumes this flag on the next
                    # dispatch and preserves session-backed recovery state.
                    continue

                if self.queue.current is not node:
                    continue

                # Stop at terminal nodes — do not advance past them
                if node.is_terminal and self.queue.current is node:
                    finalize_terminal_output(
                        node.session or self.root_session,
                        self.root_session,
                    )
                    break
                if node.is_terminal:
                    continue

                handoff = self._pop_handoff_for_next(node)
                if self._skip_ready_assessor_analyzer(node, handoff):
                    handoff = None
                self.queue.advance(handoff)
        finally:
            self._working_messages = all_messages

    def _prepend_cancellation_review(self) -> bool:
        """Fail closed when a pending cancellation escaped before execution."""
        requests = self.root_session.task_store.pending_cancellation_requests()
        if not requests:
            return False
        from tinycua.config.node_config import create_node_config
        from tinycua.loops.task_nodes import (
            TinyCUATaskAnalyzerNode,
            TinyCUATaskAssessorNode,
        )

        request_id = requests[0]["request_id"]
        assessor_config = create_node_config(
            "task_assessor", mode="cancellation_review"
        )
        assessor_config.metadata["cancellation_request_id"] = request_id
        repair_config = create_node_config("task_analyzer", mode="cancellation_repair")
        repair_config.metadata["cancellation_request_id"] = request_id
        self.queue.suspend_current_and_prepend(
            [
                TinyCUATaskAssessorNode("task_assessor", assessor_config),
                TinyCUATaskAnalyzerNode("task_analyzer", repair_config),
            ]
        )
        return True

    def _pop_handoff_for_next(self, node: Node) -> NodeHandoff | None:
        """Return an explicit handoff from the completed node to the next node."""
        next_node = self.queue.items[1] if len(self.queue.items) > 1 else None
        if next_node is None:
            return None
        if (
            node.node_id == "task_assessor"
            and node.config.metadata.get("task_assessor_mode") == "final_assessment"
        ):
            self._pending_handoffs[:] = [
                handoff
                for handoff in self._pending_handoffs
                if handoff.source_node != node.node_id
            ]
            return None
        for index, handoff in enumerate(self._pending_handoffs):
            if handoff.source_node != node.node_id:
                continue
            if handoff.target_node not in (None, next_node.node_id):
                continue
            return self._pending_handoffs.pop(index)
        return self._implicit_structured_handoff(node, next_node.node_id)

    def _skip_ready_assessor_analyzer(
        self,
        node: Node,
        handoff: NodeHandoff | None,
    ) -> bool:
        """Remove the paired analyzer when assessment says the roadmap is ready."""
        if (
            node.node_id != "task_assessor"
            or handoff is None
            or handoff.payload.get("decision") != "ready"
            or handoff.payload.get("selected_task_ids") != []
            or handoff.target_node != "task_analyzer"
            or not str(handoff.payload.get("rationale", "")).strip()
        ):
            return False
        if len(self.queue.items) > 1 and self.queue.items[1].node_id == "task_analyzer":
            self.queue.items.pop(1)
        return True

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
            content = entry_content(entry)
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
        progress_prepared = False
        if self._recovery_reentry:
            self._reset_progress_for_retry(node)
            progress_prepared = True
        if isinstance(node, TinyCUAQueryAnalystNode):
            node._queue = self.queue
        if node.contract.requires_terminate and not node.is_terminal:
            policy = node.config.stream_policy
            node_type = type(node).__name__
            async for event in self._stream_node_start(node, node_type, 1):
                yield self._enrich_and_yield(
                    event,
                    policy.include_node_metadata,
                    node.node_id,
                    node_type,
                    1,
                )
            async for event in self._stream_nonterminal_sync_node_events(
                node,
                agent,
                tools,
                override_instructions,
                node_input,
                stream_messages,
                policy.emit_internal_events,
                policy.include_node_metadata,
                policy.final_response_only,
                node_type,
                1,
                progress_prepared,
            ):
                yield event
            return
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
        progress_prepared: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute nonterminal stream nodes through sync parity path."""
        try:
            combined, tool_calls = await self._execute_node(
                node,
                agent,
                tools,
                override_instructions,
                node_input,
                progress_prepared=progress_prepared,
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
        # FR-060: re-entry signal from _execute_node's recovery path.
        if self._recovery_reentry:
            # Don't emit node.completed, don't advance — the main loop
            # will re-dispatch this node with fresh context.
            return
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
        combined, tool_calls = await self._execute_deterministic_node(
            node, resolved_tools
        )
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

    async def _stream_valid_node_completion(
        self,
        node: Node,
        combined: str,
        collected_tool_calls: list[dict[str, Any]],
        stream_messages: list[dict[str, Any]] | None,
        include_meta: bool,
        node_type: str,
        attempt_number: int,
        final_only: bool,
        emit_lifecycle: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        """Emit the valid-completion event stream for a streamed node.

        Handles the 3-branch valid block: transcript/terminal-text streaming,
        stream_messages append, and the node-completed lifecycle event.
        """
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
                stream_messages.append({"role": "assistant", "tool_calls": [tool_call]})
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
        lazy_attempts = 0  # FR-091: lazy retry counter (stream path).
        for attempt_number in range(attempt, max_attempts + 1):
            phase_before = node.progress.lifecycle_phase
            attempt_messages = self._messages_with_retry_prompt(
                base_messages,
                retry_feedback,
                retry_message,
            )
            attempt_tools = (
                self._phase_tools(node, resolved_tools, phase_before)
                if node.contract.requires_terminate
                else self._tools_for_retry_attempt(node, resolved_tools, retry_message)
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
            progress = self.root_session.node_progress.get(node.node_id)
            if (
                node.contract.requires_terminate
                and progress is not None
                and progress.lifecycle_phase != phase_before
            ):
                retry_message = self._lifecycle_phase_directive(node, resolved_tools)
                retry_feedback = self._tool_feedback_messages(llm_result)
                retry_tool_results = self._tool_results_from_llm_result(llm_result)
                continue
            if validation.is_valid:
                async for event in self._stream_valid_node_completion(
                    node,
                    combined,
                    collected_tool_calls,
                    stream_messages,
                    include_meta,
                    node_type,
                    attempt_number,
                    final_only,
                    emit_lifecycle,
                ):
                    yield event
                return
            if attempt_number < max_attempts:
                lazy_outcome = await self._maybe_lazy_in_stream_loop(  # FR-091
                    node, agent, resolved_tools, llm_result, validation, lazy_attempts
                )
                if lazy_outcome is not None:
                    lazy_result, last_validation, lazy_attempts = lazy_outcome
                    last_result = lazy_result
                    last_combined = lazy_result.content
                    if last_validation.is_valid:
                        async for event in self._stream_lazy_valid_completion(
                            node,
                            lazy_result,
                            stream_messages,
                            include_meta,
                            node_type,
                            attempt_number,
                            final_only,
                            emit_lifecycle,
                        ):
                            yield event
                        return
                    break  # terminate missing → _unbounded_recovery
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
        if self._recover_stream_completion(node, validation):
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
            async for event in self._stream_node_reentry(
                node,
                node_type,
                max_attempts,
                emit_lifecycle,
                final_only,
                include_meta,
                combined,
            ):
                yield event
            return
        lazy_outcome = await self._maybe_lazy_pre_recovery(  # FR-087..093
            node, agent, resolved_tools, llm_result, validation
        )
        if lazy_outcome is not None:
            lazy_result, revalidated, is_valid = lazy_outcome
            if is_valid:
                async for event in self._finalize_lazy_stream_recovery(
                    node,
                    lazy_result,
                    combined,
                    emit_lifecycle,
                    include_meta,
                    final_only,
                    node_type,
                    max_attempts,
                ):
                    yield event
                return
            llm_result, validation = lazy_result, revalidated
        recovery_result = await self._unbounded_recovery(
            node, agent, resolved_tools, llm_result, validation
        )
        if recovery_result is None:
            # Re-entry: yield event, return from generator.
            # Do NOT call on_complete, do NOT advance.
            async for event in self._stream_node_reentry(
                node,
                node_type,
                max_attempts,
                emit_lifecycle,
                final_only,
                include_meta,
                "Recovery budget exhausted — re-entering node with fresh context.",
            ):
                yield event
            return
        recovered_result, _ = recovery_result
        recovery_content = recovered_result.content or combined
        # Record the recovered output and fire on_complete so the queue
        # gets the next nodes (schedule_after_review / schedule_next).
        # FR-074: clear_prior=True to prevent duplicating content from
        # the failed attempt that preceded recovery.
        self._record_node_output(
            node,
            recovery_content,
            recovered_result.tool_calls,
            clear_prior=True,
        )
        recovered_result.metadata = dict(recovered_result.metadata)
        if recovery_content:
            self._record_node_content_transcript(node, recovery_content)
        self._record_tool_result_transcripts(
            node,
            recovered_result.metadata.get("tool_results", []),
            recovered_result.tool_calls,
        )
        self._apply_loop_result_hook(node, recovered_result, None)
        self._publish_structured_outputs_to_root(node)
        self._maybe_populate_root_mission(node)
        self._apply_task_lifecycle_marker(node, recovery_content)
        on_complete_response = self._build_on_complete_response(node, recovered_result)
        node.on_complete(self.queue, on_complete_response)
        self._publish_structured_outputs_to_root(node)
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

    def _recover_stream_completion(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> bool:
        """Recover stream failures that can complete without node re-entry."""
        return self._recover_task_assessor_validation_failure(
            node, validation
        ) or self._recover_task_analyzer_validation_failure(node, validation)

    async def _stream_node_reentry(
        self,
        node: Node,
        node_type: str,
        attempt: int,
        emit_lifecycle: bool,
        final_only: bool,
        include_meta: bool,
        content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Emit retry re-entry without completing the current node."""
        event = self._emit_lifecycle_event(
            "node.reentry",
            node.node_id,
            node_type,
            attempt,
            emit_lifecycle,
            final_only,
            node.is_terminal,
            content=content,
            finish_reason="reentry",
        )
        if event is not None:
            yield self._enrich_and_yield(
                event,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )
        if content:
            self._record_node_content_transcript(node, content)

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
