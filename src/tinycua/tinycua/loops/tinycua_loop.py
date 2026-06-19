"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.agent.loop import BaseLoop

from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops._loop_constants import _MAX_TOOL_CONTINUATIONS
from tinycua.loops.context_rendering import render_llm_content, sanitize_internal_reprs
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.node_handoff import NodeHandoff
from tinycua.loops.orchestration_mixin import OrchestrationMixin
from tinycua.loops.prompt_protocol_mixin import PromptProtocolMixin
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.task_tree_rendering import render_task_tree
from tinycua.loops.trace_state_mixin import TraceStateMixin
from tinycua.loops.validation_retry_mixin import ValidationRetryMixin
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.config.types import AgentMonitor
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class TinyCUALoop(
    OrchestrationMixin,
    ValidationRetryMixin,
    PromptProtocolMixin,
    TraceStateMixin,
    BaseLoop,
):
    """Execution loop for TinyCUA agents.

    Extends the SDK BaseLoop with node-based execution, session management,
    chat history recording, message merging, tool scoping, and streaming.
    """

    def __init__(
        self,
        root_session: Session | None = None,
        queue: NodeQueue | None = None,
        session_config: SessionConfig | None = None,
        default_terminal_node: Node | None = None,
        agent_monitor: AgentMonitor | None = None,
        queue_factory: Callable[[], NodeQueue] | None = None,
    ) -> None:
        """Initialize TinyCUALoop.

        Args:
            root_session: The root session for this loop. Created if not provided.
            queue: Node queue for execution. Created if not provided.
            session_config: Session configuration to apply.
            default_terminal_node: Default terminal node for ensure_terminal() bootstrap.
            agent_monitor: Optional agent-level monitor hook for observing node execution.
            queue_factory: Optional factory used to create a fresh run queue per call.
        """
        super().__init__(0)
        self.__dict__.pop("max_" + "iterations", None)
        self.root_session = root_session or Session()
        self.queue = queue or NodeQueue()
        self.session_config = session_config
        self.default_terminal_node = default_terminal_node
        self.agent_monitor = agent_monitor
        self.queue_factory = queue_factory
        self._working_messages: list[dict[str, Any]] = []
        self._usage_events: list[dict[str, Any]] = []
        self._execution_trace: list[dict[str, Any]] = []
        self._final_response_events: list[dict[str, Any]] = []
        self._transcript_events: list[dict[str, Any]] = []
        self._transcript_seen_node_contents: set[str] = set()
        self.workspace_dir = getattr(session_config, "workspace_dir", None)
        self.artifact_dir = getattr(session_config, "artifact_dir", None)
        self.session_dir = getattr(session_config, "session_dir", None)
        self._tool_artifact_seq = 0
        self._pending_handoffs: list[NodeHandoff] = []
        self._resolved_tools_for_prompt: list[Tool] | None = None

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

    def get_usage_events(self) -> list[dict[str, Any]]:
        """Return the usage events captured during the last streaming run.

        Usage events include token counts and other billing metadata
        from the LLM response. Only populated when using streaming mode.

        Returns:
            List of usage event dicts from the last streaming execution.
        """
        return list(self._usage_events)

    def get_execution_trace(self) -> list[dict[str, Any]]:
        """Return node execution trace from the latest run."""
        return list(self._execution_trace)

    def get_final_response_events(self) -> list[dict[str, Any]]:
        """Return user-visible final-response events from the latest run."""
        return list(self._final_response_events)

    def get_transcript_events(self) -> list[dict[str, Any]]:
        """Return readable node/user/tool transcript events from the latest run."""
        return list(self._transcript_events)

    def get_transcript_text(self, *, include_node_calls: bool = False) -> str:
        """Return grouped transcript text suitable for notebook/CLI display."""
        lines: list[str] = []
        current_key: tuple[str | None, str | None, str] | None = None
        current_parts: list[str] = []

        def flush() -> None:
            nonlocal current_key, current_parts
            if current_key is None:
                return
            node_id, tool_name, label = current_key
            del node_id
            prefix = f"[{label}]"
            if tool_name:
                prefix += f"[{tool_name}]"
            content = "".join(current_parts).strip()
            if content:
                lines.append(f"{prefix} {content}")
            current_key = None
            current_parts = []

        for event in self._transcript_events:
            if event.get("type") == "transcript.node_call" and not include_node_calls:
                continue
            label = str(event.get("node_label") or "NODE")
            key = (event.get("node_id"), event.get("tool_name"), label)
            content = str(event.get("content") or "")
            if event.get("type") == "transcript.delta":
                if current_key != key:
                    flush()
                    current_key = key
                current_parts.append(content)
                continue
            flush()
            prefix = f"[{label}]"
            tool_name = event.get("tool_name")
            if tool_name:
                prefix += f"[{tool_name}]"
            if content:
                lines.append(f"{prefix} {content}")
        flush()
        return "\n".join(lines)

    def render_task_tree(self, store=None) -> str:
        """Render the current or provided task tree as readable text."""
        return render_task_tree(store or self.root_session.task_store)

    def get_task_trace(self) -> list[dict[str, Any]]:
        """Return task-state snapshots captured in execution trace entries."""
        return [
            entry["task_tree"]
            for entry in self._execution_trace
            if "task_tree" in entry
        ]

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot of runtime-visible state."""
        return {
            "session_id": self.root_session.session_id,
            "task_tree": self.root_session.task_store.snapshot(),
            "task_tree_text": self.render_task_tree(),
            "transcript_text": self.get_transcript_text(),
            "todo": list(self.root_session.todo),
            "workspace_dir": str(self.workspace_dir) if self.workspace_dir else None,
            "artifact_dir": str(self.artifact_dir) if self.artifact_dir else None,
        }

    def get_active_task(self):
        """Return the current active task from the root session task store."""
        return self.root_session.task_store.get_active_task()

    def set_active_task(self, task_id: str) -> None:
        """Set the active task id after validating that the task exists."""
        self.root_session.task_store.get_task(task_id)
        self.root_session.task_store.active_task_id = task_id

    def update_active_task_result(
        self,
        summary: str,
        *,
        success: bool = True,
        artifacts: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a result for the current active task."""
        from tinycua.models.task import TaskResult

        active = self.get_active_task()
        if active is None:
            msg = "No active task"
            raise ValueError(msg)
        self.root_session.task_store.record_result(
            active.task_id,
            TaskResult(
                task_id=active.task_id,
                content=summary,
                summary=summary,
                success=success,
                artifacts=artifacts or [],
                metadata=metadata or {},
            ),
        )

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
        self._execution_trace = []
        self._final_response_events = []
        self._transcript_events = []
        self._transcript_seen_node_contents = set()
        for message in messages:
            if message.get("role") == "user":
                self._record_transcript_event(
                    "transcript.user",
                    "USER",
                    str(message.get("content", "")),
                    node_id=None,
                )

        # Each public run starts from the configured entry graph. Durable state
        # lives on ``root_session``; consumed queue nodes do not persist across
        # invocations of a reused agent instance.
        if self.queue_factory is not None:
            self.queue = self.queue_factory()
            self.default_terminal_node = (
                self.queue.items[-1] if self.queue.items else None
            )

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
        """Run by consuming the canonical streaming runtime.

        Streaming is the source of truth for node preparation, execution,
        validation, tool execution, queue mutation, transcript recording, and
        terminal handling. Synchronous execution only drains that stream and
        returns the terminal response text.
        """
        final_chunks: list[str] = []
        async for event in self._run_stream(agent, tools, override_instructions):
            if (
                event.get("type") == "response.output_text.delta"
                and event.get("node_id") == "response"
            ):
                final_chunks.append(str(event.get("delta", "")))
        if final_chunks:
            return "".join(final_chunks)
        return self._terminal_response_from_state()

    def _terminal_response_from_state(self) -> str:
        """Return terminal response text recorded by the streaming runtime."""
        for event in reversed(self._final_response_events):
            if event.get("type") == "response.output_text.done":
                return str(event.get("content", ""))
            if event.get("type") == "response.output_text.delta":
                return str(event.get("delta", ""))
        for entry in reversed(self.root_session.session_context):
            source = getattr(entry, "source_node_id", None)
            segment = getattr(entry, "segment", None)
            if source == "response" and segment == "output":
                return render_llm_content(getattr(entry, "content", ""))
        return ""

    def _normalize_system_messages(
        self, messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Collapse all system messages into a single leading system message."""
        system_parts = [
            str(m.get("content", ""))
            for m in messages
            if m.get("role") == "system" and str(m.get("content", "")).strip()
        ]
        non_system = [m for m in messages if m.get("role") != "system"]
        if not system_parts:
            return non_system
        return [{"role": "system", "content": "\n\n".join(system_parts)}, *non_system]

    def _bind_session_tools(self, tools: list[Tool], node: Node) -> None:
        """Bind session-aware tools to this loop's root session state."""
        for tool in tools:
            binder = getattr(tool, "bind_task_store", None)
            if callable(binder):
                binder(self.root_session.task_store)
            todo_binder = getattr(tool, "bind_todo_store", None)
            if callable(todo_binder):
                todo_binder(self.root_session.todo)
            workspace_binder = getattr(tool, "bind_workspace", None)
            if callable(workspace_binder):
                workspace_binder(self.workspace_dir)
            handoff_binder = getattr(tool, "bind_handoff_store", None)
            if callable(handoff_binder):
                handoff_binder(self._pending_handoffs)
            source_binder = getattr(tool, "bind_source_node", None)
            if callable(source_binder):
                source_binder(node.node_id)

    async def _execute_tool_calls(
        self,
        agent: Agent,
        tool_calls: list[dict[str, Any]],
        resolved_tools: list[Tool],
    ) -> list[dict[str, Any]]:
        """Execute allowed tool calls against the active session state."""
        allowed_tools = {tool.name: tool for tool in resolved_tools}
        results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = function.get("name") or tool_call.get("name")
            if not name:
                continue
            if name not in allowed_tools:
                results.append(
                    {"name": name, "allowed": False, "error": "tool_not_allowed"}
                )
                continue
            if not callable(allowed_tools[name]):
                continue
            arguments = function.get("arguments") or tool_call.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments else {}
                except json.JSONDecodeError as exc:
                    results.append({"name": name, "allowed": True, "error": str(exc)})
                    continue
            if not isinstance(arguments, dict):
                results.append(
                    {"name": name, "allowed": True, "error": "arguments_not_object"}
                )
                continue
            arguments = self._normalize_tool_call_arguments(allowed_tools[name], arguments)
            try:
                output = await ToolExecutor.execute(allowed_tools[name], arguments, agent)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001 - recorded for trace/debugging.
                results.append({"name": name, "allowed": True, "error": str(exc)})
                continue
            self._sync_root_task()
            tool_result = {"name": name, "allowed": True, "output": output}
            artifact_path = self._write_tool_audit_artifact(name, arguments, output)
            if artifact_path:
                tool_result["artifact_path"] = artifact_path
            self._record_tool_chat_result(tool_result)
            results.append(tool_result)
        return results

    def _normalize_tool_call_arguments(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize provider-emitted argument wrappers without hiding schema data."""
        nested = arguments.get("arguments")
        if set(arguments) != {"arguments"} or not isinstance(nested, dict):
            return arguments
        parameters = getattr(tool, "parameters", {})
        properties = parameters.get("properties", {}) if isinstance(parameters, dict) else {}
        if isinstance(properties, dict) and "arguments" in properties:
            return arguments
        return nested

    def _write_tool_audit_artifact(
        self,
        name: str,
        arguments: dict[str, Any],
        output: Any,
    ) -> str | None:
        """Write a durable audit JSON for action/research tool calls."""
        if self.artifact_dir is None:
            return None
        if name not in {"run_shell", "run_python", "web_search", "fetch_url"}:
            return None
        self._tool_artifact_seq += 1
        audit_dir = self.artifact_dir / "tool-calls"
        audit_dir.mkdir(parents=True, exist_ok=True)
        path = audit_dir / f"{self._tool_artifact_seq:04d}-{name}.json"
        path.write_text(
            json.dumps({"name": name, "arguments": arguments, "output": output}, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

    def _enrich_task_results_from_tool_batch(
        self,
        node: Node,
        tool_results: list[dict[str, Any]],
    ) -> None:
        """Attach tool-call transcript evidence to recorded task results."""
        if node.node_id != "task_executor":
            return
        for item in tool_results:
            if item.get("name") != "task_result_update":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("success") is not True:
                continue
            task_id = output.get("task_id")
            if not isinstance(task_id, str):
                continue
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                continue
            partial_results = list(
                task.metadata.get("executor_partial_tool_results", [])
            )
            merged_tool_results = [*partial_results, *tool_results]
            evidence = self._json_safe(merged_tool_results)
            if task.result is not None:
                task.result.metadata["tool_results"] = evidence
                task.metadata.pop("executor_partial_tool_results", None)

    async def _call_node_with_retry(
        self,
        node: Node,
        agent: Agent,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
    ) -> tuple[LLMResult, int, ValidationResult]:
        """Loop-owned LLM call, validation, and retry lifecycle."""
        max_attempts = self._effective_max_attempts(node)
        last_result = LLMResult()
        last_validation = ValidationResult(is_valid=True, errors=[])
        base_messages = [dict(message) for message in messages]
        retry_message: str | None = None
        retry_feedback: list[dict[str, Any]] = []
        retry_tool_results: list[dict[str, Any]] = []

        for attempt in range(1, max_attempts + 1):
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
            raw_response = await self._call_agent_llm(
                agent,
                node,
                attempt_messages,
                attempt_tools,
            )
            last_result = LLMResult(
                content=sanitize_internal_reprs(raw_response.get("content") or ""),
                role=raw_response.get("role", "assistant"),
                tool_calls=raw_response.get("tool_calls") or [],
                metadata=raw_response.get("metadata", {}),
            )
            if not node.is_terminal and node.node_id != "result_aggregation":
                self._coerce_structured_tool_calls(last_result, attempt_tools)
            self._coerce_terminate_only_response(attempt_tools, last_result)
            all_tool_results: list[dict[str, Any]] = []
            continuation_rounds = 0
            while continuation_rounds < _MAX_TOOL_CONTINUATIONS:
                tool_results = await self._execute_tool_calls(
                    agent,
                    last_result.tool_calls,
                    attempt_tools,
                )
                if not tool_results:
                    break
                all_tool_results.extend(tool_results)
                self._enrich_task_results_from_tool_batch(node, all_tool_results)
                normalized_tool_calls = self._normalize_tool_calls(
                    last_result.tool_calls
                )
                last_result.tool_calls = normalized_tool_calls
                last_result.metadata = dict(last_result.metadata)
                last_result.metadata["tool_results"] = list(all_tool_results)
                self._prepend_retry_tool_results(last_result, retry_tool_results)
                self._fill_content_from_recorded_task_result(last_result)
                last_validation = self._validate_node_result(node, last_result)
                if self._can_stop_after_tool_batch(node, last_result, last_validation):
                    return last_result, attempt, last_validation
                if self._validation_needs_terminate(last_validation):
                    break
                attempt_messages.append(
                    {
                        "role": "assistant",
                        "content": last_result.content,
                        "tool_calls": normalized_tool_calls,
                    }
                )
                for index, tool_result in enumerate(tool_results):
                    tool_call = (
                        normalized_tool_calls[index]
                        if index < len(normalized_tool_calls)
                        else {}
                    )
                    attempt_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id")
                            or tool_result.get("name", ""),
                            "name": tool_result.get("name", ""),
                            "content": json.dumps(tool_result, default=str),
                        }
                    )
                continuation_rounds += 1
                if continuation_rounds >= _MAX_TOOL_CONTINUATIONS:
                    break
                raw_response = await self._call_agent_llm(
                    agent,
                    node,
                    attempt_messages,
                    attempt_tools,
                )
                last_result = LLMResult(
                    content=sanitize_internal_reprs(raw_response.get("content") or ""),
                    role=raw_response.get("role", "assistant"),
                    tool_calls=raw_response.get("tool_calls") or [],
                    metadata={
                        **raw_response.get("metadata", {}),
                        "tool_results": list(all_tool_results),
                    },
                )
                if not node.is_terminal and node.node_id != "result_aggregation":
                    self._coerce_structured_tool_calls(last_result, attempt_tools)
                self._coerce_terminate_only_response(attempt_tools, last_result)
            if all_tool_results:
                last_result.metadata = dict(last_result.metadata)
                last_result.metadata["tool_results"] = list(all_tool_results)
                self._prepend_retry_tool_results(last_result, retry_tool_results)
                self._fill_content_from_recorded_task_result(last_result)
            last_validation = self._validate_node_result(node, last_result)
            if last_validation.is_valid:
                return last_result, attempt, last_validation
            if attempt < max_attempts:
                error = ValidationError("; ".join(last_validation.errors))
                retry_message = self._retry_message_for_validation(
                    error,
                    node,
                    resolved_tools,
                    last_result,
                )
                retry_feedback = self._tool_feedback_messages(last_result)
                retry_tool_results = self._tool_results_from_llm_result(last_result)
                self._record_retry_continuation(node, retry_message, attempt)

        node._handle_exhaustion(last_validation, max_attempts)
        return last_result, max_attempts, last_validation

    async def _call_agent_llm(
        self,
        agent: Agent,
        node: Node,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
        *,
        stream: bool = False,
        force_required_tool: bool = True,
    ) -> Any:
        """Call the SDK agent, optionally forcing a node-required route tool.

        The SDK reads ``tool_choice`` from the immutable ``LanguageModel``
        bound to the agent/client. TinyCUA keeps this reliability hook outside
        SDK source by temporarily swapping the model value and cached client for
        only this call, then restoring both immediately afterward.
        """
        tool_choice = None
        if force_required_tool:
            tool_choice = self._forced_tool_choice_for_node(agent, node, resolved_tools)
        llm_tools = self._llm_tools_for_required_choice(
            node,
            resolved_tools,
            force_required_tool=tool_choice is not None,
        )
        config = getattr(agent, "config", None)
        model = getattr(config, "llm_model", None)
        model_overrides: dict[str, Any] = {}
        max_tokens = self._node_max_tokens_override(node, model)
        if max_tokens is not None:
            model_overrides["max_tokens"] = max_tokens
        if tool_choice is not None:
            model_overrides["tool_choice"] = tool_choice

        if not model_overrides:
            return await self._invoke_agent_llm(
                agent,
                messages,
                llm_tools,
                stream=stream,
            )

        if model is None or not hasattr(model, "model_copy"):
            return await self._invoke_agent_llm(
                agent,
                messages,
                llm_tools,
                stream=stream,
            )

        previous_model = config.llm_model
        had_client_attr = hasattr(agent, "_llm_client")
        previous_client = getattr(agent, "_llm_client", None)
        config.llm_model = model.model_copy(update=model_overrides)
        if had_client_attr:
            agent._llm_client = None  # type: ignore[attr-defined]
        try:
            return await self._invoke_agent_llm(
                agent,
                messages,
                llm_tools,
                stream=stream,
            )
        finally:
            config.llm_model = previous_model
            if had_client_attr:
                agent._llm_client = previous_client  # type: ignore[attr-defined]

    def _node_max_tokens_override(self, node: Node, model: Any) -> int | None:
        """Let the server decide max tokens — no client-side override."""
        return None

    async def _invoke_agent_llm(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
        *,
        stream: bool = False,
    ) -> Any:
        """Invoke agent._call_llm while supporting async iterators in tests."""
        messages = self._normalize_system_messages(messages)
        result = agent._call_llm(messages, resolved_tools, stream=stream)  # type: ignore[arg-type]
        if inspect.isawaitable(result):
            result = await result
        if not stream and hasattr(result, "__aiter__"):
            return await self._collect_async_stream_result(result)
        return result

    async def _collect_async_stream_result(self, stream_result: Any) -> dict[str, Any]:
        """Collect an async stream into a non-stream response dict."""
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        async for event in stream_result:
            event_type = event.get("type") if isinstance(event, dict) else None
            if event_type == "response.output_text.delta":
                content_parts.append(str(event.get("delta", "")))
            elif event_type == "response.tool_call":
                tool_calls.append(event)
            elif event_type == "tool_call.ready":
                tool_calls.append(
                    {
                        "id": event.get("id") or event.get("call_id"),
                        "type": "function",
                        "function": {
                            "name": event.get("name", ""),
                            "arguments": event.get("arguments", "{}"),
                        },
                    }
                )
            elif event_type == "response.usage":
                metadata["usage"] = event.get("usage")
        return {
            "role": "assistant",
            "content": "".join(content_parts),
            "tool_calls": tool_calls,
            "metadata": metadata,
        }

    async def _collect_stream_events(
        self,
        node: Node,
        agent: Agent,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
        content_parts: list[str],
        collected_tool_calls: list[dict[str, Any]],
        include_meta: bool,
        final_only: bool,
        node_type: str,
        attempt: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Collect provider stream events and yield policy-filtered events."""
        # ponytail: LM Studio can ignore forced single-tool calls while streaming;
        # terminate has no user-visible text, so use non-stream for that retry.
        stream = [tool.name for tool in resolved_tools] != ["terminate"]
        stream_result = await self._call_agent_llm(
            agent,
            node,
            messages,
            resolved_tools,
            stream=stream,
        )
        async for event in self._iter_stream_result_events(stream_result):
            if node.is_terminal and event.get("type") == "response.output_text.delta":
                content_parts.append(str(event.get("delta", "")))
                continue
            transcript = self._handle_stream_event(
                node,
                event,
                content_parts,
                collected_tool_calls,
            )
            enriched = self._enrich_and_yield(
                event,
                include_meta,
                node.node_id,
                node_type,
                attempt,
            )
            if not final_only or node.is_terminal:
                yield enriched
                if transcript is not None:
                    yield transcript

    async def _iter_stream_result_events(
        self,
        stream_result: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield provider events, adapting non-stream responses when needed."""
        if hasattr(stream_result, "__aiter__"):
            async for event in stream_result:
                yield event
            return
        if isinstance(stream_result, dict):
            content = sanitize_internal_reprs(str(stream_result.get("content") or ""))
            if content:
                yield {"type": "response.output_text.delta", "delta": content}
            for tool_call in stream_result.get("tool_calls") or []:
                if isinstance(tool_call, dict):
                    function = tool_call.get("function") or {}
                    yield {
                        "type": "tool_call.ready",
                        "id": tool_call.get("id"),
                        "name": function.get("name") or tool_call.get("name", ""),
                        "arguments": function.get("arguments")
                        or tool_call.get("arguments", "{}"),
                    }
            metadata = stream_result.get("metadata")
            if isinstance(metadata, dict) and metadata.get("usage"):
                yield {"type": "response.usage", "usage": metadata["usage"]}
            yield {"type": "response.completed", "finish_reason": "completed"}
            return
        if isinstance(stream_result, str):
            yield {"type": "response.output_text.delta", "delta": stream_result}
        yield {"type": "response.completed", "finish_reason": "completed"}

    async def _stream_terminal_text(
        self,
        content: str,
        include_meta: bool,
        node_id: str,
        node_type: str,
        attempt: int,
        final_only: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        """Emit validated terminal text once."""
        del final_only
        event = {"type": "response.output_text.delta", "delta": content}
        self._final_response_events.append(dict(event))
        transcript = self._record_transcript_event(
            "transcript.delta",
            "Response",
            content,
            node_id=node_id,
        )
        yield self._enrich_and_yield(event, include_meta, node_id, node_type, attempt)
        yield transcript

    def _handle_stream_event(
        self,
        node: Node,
        event: dict[str, Any],
        content_parts: list[str],
        collected_tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Update stream accumulators from one provider event."""
        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            delta = event.get("delta", "")
            content_parts.append(delta)
            if node.is_terminal:
                self._final_response_events.append(dict(event))
                return self._record_transcript_event(
                    "transcript.delta",
                    self._node_label(node),
                    delta,
                    node_id=node.node_id,
                )
        elif event_type == "response.tool_call":
            collected_tool_calls.append(event)
        elif event_type == "tool_call.ready":
            collected_tool_calls.append(
                {
                    "id": event.get("id") or event.get("call_id"),
                    "type": "function",
                    "function": {
                        "name": event.get("name", ""),
                        "arguments": event.get("arguments", "{}"),
                    },
                }
            )
        elif event_type == "response.usage":
            self._usage_events.append(event)
        return None
