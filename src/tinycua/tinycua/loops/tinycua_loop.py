"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import AsyncIterator, Callable
from enum import Enum
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.config.system_prompt import SystemPromptBuilder
from tinycua.models.stream_event import enrich_stream_event, make_lifecycle_event
from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops.context_rendering import (
    render_llm_content,
    sanitize_internal_reprs,
    should_include_chat_record,
)
from tinycua.loops.node import (
    DecisionNode,
    DecisionResult,
    NodeExecutionError,
    NodeRunContext,
    build_messages_with_dedupe,
)
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.propagation import (
    PropagationRule,
    finalize_terminal_output,
    propagate_on_termination,
)
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.route_classifier import RouteClassifier
from tinycua.loops.task_tree_rendering import render_task_tree
from tinycua.models.node_input import convert_node_input_to_messages
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.config.types import AgentMonitor
    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)

_MAX_TOOL_CONTINUATIONS = 6
_UNBOUNDED_RETRY_ATTEMPTS = 1_000_000_000


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

    def _next_terminal_node(self) -> Node | None:
        """Return an existing or configured terminal node for forced routing."""
        for item in self.queue.items:
            if item.is_terminal:
                return item
        return self.default_terminal_node

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
        messages = self._build_node_messages(node, override_instructions)
        resolved_tools = node.config.tool_policy.resolve_tools(tools)
        self._bind_session_tools(resolved_tools)
        if resolved_tools:
            messages.append(
                {
                    "role": "system",
                    "content": self._tool_call_protocol_message(resolved_tools),
                }
            )
        return messages, resolved_tools

    def _tool_call_protocol_message(self, resolved_tools: list[Tool]) -> str:
        """Return provider-agnostic tool-call instructions for local LLMs."""
        tool_names = ", ".join(tool.name for tool in resolved_tools)
        return (
            "Tool-use contract: call available tools through native tool calling "
            "whenever the provider supports it. If native tool calls are not "
            "available, respond with ONLY strict JSON in this shape: "
            '{"tool_calls":[{"name":"tool_name","arguments":{}}]}. '
            f"Available tool names: {tool_names}. Do not wrap this JSON in "
            "Markdown and do not include prose when making tool calls."
        )

    def _bind_session_tools(self, tools: list[Tool]) -> None:
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

    def _execute_tool_calls(
        self,
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
                output = allowed_tools[name](**arguments)  # type: ignore[misc,operator]
            except Exception as exc:  # noqa: BLE001 - recorded for trace/debugging.
                results.append({"name": name, "allowed": True, "error": str(exc)})
                continue
            self._sync_root_task()
            tool_result = {"name": name, "allowed": True, "output": output}
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

    def _enrich_task_results_from_tool_batch(
        self,
        node: Node,
        tool_results: list[dict[str, Any]],
    ) -> None:
        """Attach observed artifacts/tool evidence to recorded task results."""
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
            artifacts = self._artifacts_from_tool_results(merged_tool_results)
            evidence = self._json_safe(merged_tool_results)
            if task.result is not None:
                task.result.metadata["tool_results"] = evidence
                existing_result_paths = {
                    artifact.get("path") for artifact in task.result.artifacts
                }
                for artifact in artifacts:
                    if artifact.get("path") not in existing_result_paths:
                        task.result.artifacts.append(artifact)
                        existing_result_paths.add(artifact.get("path"))
                task.metadata.pop("executor_partial_tool_results", None)
            existing_task_paths = {artifact.get("path") for artifact in task.artifacts}
            for artifact in artifacts:
                if artifact.get("path") not in existing_task_paths:
                    task.artifacts.append(artifact)
                    existing_task_paths.add(artifact.get("path"))

    def _downgrade_unsupported_executor_success(
        self,
        task: Any,
        tool_results: list[dict[str, Any]],
    ) -> None:
        """Turn unsupported executor success into a non-successful result."""
        if task.result is None or task.result.success is not True:
            return
        if self._has_concrete_executor_action_evidence(tool_results):
            return
        original_content = task.result.content
        task.result.success = False
        task.result.execution_status = "failed"
        task.result.metadata["runtime_success_rejected"] = {
            "reason": (
                "TaskExecutor recorded success=True without concrete action "
                "evidence from write_file, edit_file, run_shell, or run_python."
            ),
            "tool_results": self._json_safe(tool_results),
        }
        task.result.content = (
            "Runtime rejected the successful task_result_update because no "
            "concrete implementation evidence was observed. Original claimed "
            f"result: {original_content}"
        )
        task.result.summary = task.result.content

    def _artifacts_from_tool_results(
        self,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract durable artifact references from tool execution results."""
        artifacts: list[dict[str, Any]] = []
        for item in tool_results:
            if item.get("name") != "write_file":
                continue
            output = item.get("output")
            if not isinstance(output, dict):
                continue
            if output.get("success") is True and output.get("path"):
                artifacts.append(
                    {
                        "path": str(output["path"]),
                        "kind": "file",
                        "metadata": {"tool_name": "write_file"},
                    }
                )
        return artifacts

    def _node_label(self, node: Node) -> str:
        """Return a compact human-readable node label."""
        label = type(node).__name__
        for prefix in ("TinyCUA",):
            if label.startswith(prefix):
                label = label[len(prefix) :]
        for suffix in ("Node",):
            if label.endswith(suffix):
                label = label[: -len(suffix)]
        if label == "QueryAnalyst":
            return "QueryAnalyst"
        return label or node.node_id

    def _record_transcript_event(
        self,
        event_type: str,
        node_label: str,
        content: str,
        *,
        node_id: str | None,
        tool_name: str | None = None,
    ) -> dict[str, Any]:
        """Record a readable transcript event."""
        content = sanitize_internal_reprs(content)
        prefix = f"[{node_label}]"
        if tool_name:
            prefix += f"[{tool_name}]"
        event = {
            "type": event_type,
            "node_id": node_id,
            "node_type": node_label,
            "node_label": node_label,
            "tool_name": tool_name,
            "attempt": 1,
            "content": content,
            "delta": f"{prefix} {content}" if content else prefix,
        }
        self._transcript_events.append(event)
        return event

    def _record_tool_chat_result(self, tool_result: dict[str, Any]) -> None:
        """Append a durable internal chat-history record for a tool result."""
        from tinycua.models.chat_record import ChatRecord

        self.root_session.chat_history.append(
            ChatRecord(
                role="tool",
                record_type="tool_result",
                content=tool_result,
                visibility="tool_only",
                source_session_id=self.root_session.session_id,
                created_seq=len(self.root_session.chat_history),
                metadata={"tool_name": tool_result.get("name")},
            )
        )

    def _record_tool_result_transcripts(
        self,
        node: Node,
        tool_results: list[dict[str, Any]],
    ) -> None:
        """Record readable transcript events for executed tool results."""
        for tool_result in tool_results:
            self._record_transcript_event(
                "transcript.tool_result",
                self._node_label(node),
                json.dumps(tool_result, default=str),
                node_id=node.node_id,
                tool_name=str(tool_result.get("name", "tool")),
            )

    def _sync_root_task(self) -> None:
        """Expose the current root task on the public session object."""
        root_id = self.root_session.task_store.root_task_id
        if root_id is not None:
            self.root_session.task = self.root_session.task_store.tasks.get(root_id)

    def _task_state_snapshot(self) -> dict[str, Any] | None:
        """Return a serializable task-tree snapshot for trace entries."""
        store = self.root_session.task_store
        if not store.tasks:
            return None
        return store.snapshot()

    def _json_safe(self, value: Any) -> Any:
        """Convert trace values to JSON-serializable primitives."""
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value

    def _apply_task_lifecycle_marker(self, node: Node, content: str) -> None:
        """Synchronize public task pointer after tool-owned state changes."""
        del node, content
        self._sync_root_task()

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
        if content and node.is_terminal:
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
            all_tool_results: list[dict[str, Any]] = []
            continuation_rounds = 0
            while continuation_rounds < _MAX_TOOL_CONTINUATIONS:
                tool_results = self._execute_tool_calls(
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
                    force_required_tool=False,
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
                retry_message = self._natural_retry_message(
                    error,
                    node,
                    resolved_tools,
                )
                retry_feedback = self._tool_feedback_messages(last_result)
                retry_tool_results = self._tool_results_from_llm_result(last_result)
                self._record_retry_continuation(node, retry_message, attempt)

        node._handle_exhaustion(last_validation, max_attempts)
        return last_result, max_attempts, last_validation

    def _messages_with_retry_prompt(
        self,
        base_messages: list[dict[str, Any]],
        retry_feedback: list[dict[str, Any]],
        retry_message: str | None,
    ) -> list[dict[str, Any]]:
        """Return base node messages, latest tool feedback, and one retry prompt."""
        messages = [dict(message) for message in base_messages]
        messages.extend(dict(message) for message in retry_feedback)
        if retry_message:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Retry prompt: {retry_message} Make the required tool "
                        "call now; do not repeat this text."
                    ),
                }
            )
        return messages

    def _tools_for_retry_attempt(
        self,
        node: Node,
        resolved_tools: list[Tool],
        retry_message: str | None,
    ) -> list[Tool]:
        """Narrow retry tools when validation names one required state tool."""
        required = self._retry_required_tool_name(node, retry_message)
        if required is None:
            return resolved_tools
        narrowed = [tool for tool in resolved_tools if tool.name == required]
        return narrowed or resolved_tools

    def _retry_required_tool_name(
        self,
        node: Node,
        retry_message: str | None,
    ) -> str | None:
        """Return a required tool that should be isolated for this retry."""
        if not retry_message:
            return None
        retry_required_by_node = {
            "task_analyzer": "task_decompose",
            "result_reviewer": "task_review_decision",
        }
        required = retry_required_by_node.get(node.node_id)
        if required and required in retry_message:
            return required
        return None

    def _prepend_retry_tool_results(
        self,
        llm_result: LLMResult,
        retry_tool_results: list[dict[str, Any]],
    ) -> None:
        """Expose latest retry feedback tool results to current validation."""
        if not retry_tool_results:
            return
        current = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        llm_result.metadata["tool_results"] = [*retry_tool_results, *current]

    def _tool_results_from_llm_result(
        self,
        llm_result: LLMResult,
    ) -> list[dict[str, Any]]:
        """Return successful/failed tool result records carried by an LLM result."""
        return [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]

    def _fill_content_from_recorded_task_result(self, llm_result: LLMResult) -> None:
        """Populate empty content from successful task_result_update state."""
        if llm_result.content.strip():
            return
        for item in reversed(llm_result.metadata.get("tool_results", [])):
            if not isinstance(item, dict) or item.get("name") != "task_result_update":
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
            if task.result is not None and task.result.content.strip():
                llm_result.content = task.result.content
                return

    def _route_task_executor_failure_to_reviewer(
        self,
        node: Node,
        validation: ValidationResult,
        llm_result: LLMResult,
    ) -> bool:
        """TaskExecutor validation failures are not reviewer-owned results."""
        del node, validation, llm_result
        return False

    def _recover_task_executor_validation_failure(
        self,
        node: Node,
        validation: ValidationResult,
        llm_result: LLMResult,
    ) -> bool:
        """Recover exhausted TaskExecutor validation via local replan.

        Runtime validation failures are not task results. In one-shot worker
        mode, the active task remains unfinished and the runtime gives the
        planner a chance to revise/decompose the local task region before
        execution continues.
        """
        if node.node_id != "task_executor" or node.is_terminal:
            return False
        if self.queue.current is not node:
            return False
        active = self.root_session.task_store.get_active_task()
        if active is None:
            return False
        tool_results = list(llm_result.metadata.get("tool_results", []))
        action_results = self._successful_executor_action_results(tool_results)
        if action_results:
            existing = active.metadata.setdefault("executor_partial_tool_results", [])
            existing.extend(self._json_safe(action_results))
            self._record_node_content_transcript(
                node,
                "TaskExecutor performed workspace/research actions but did not "
                "record task_result_update; continuing the same active task with "
                "partial evidence instead of replanning or marking failure.",
            )
            terminal_nodes = [queued for queued in self.queue.items[1:] if queued.is_terminal]
            self.queue.clear_after_current()
            from tinycua.config.node_config import create_node_config
            from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
            from tinycua.loops.task_nodes import TinyCUATaskExecutorNode

            self.queue.items.extend(
                [
                    TinyCUATaskExecutorNode(
                        node_id="task_executor",
                        config=create_node_config("task_executor"),
                    ),
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer"),
                    ),
                ]
            )
            existing_terminal_ids = {
                queued.node_id for queued in self.queue.items if queued.is_terminal
            }
            for terminal in terminal_nodes:
                if terminal.node_id not in existing_terminal_ids:
                    self.queue.items.append(terminal)
                    existing_terminal_ids.add(terminal.node_id)
            return True
        active.metadata["runtime_validation_failure"] = {
            "source_node_id": node.node_id,
            "errors": list(validation.errors),
            "recovery": "executor_retry",
            "tool_results": self._json_safe(tool_results),
            "guidance": (
                "Previous executor attempt did not record task_result_update. "
                "Retry the active task and call task_result_update with the "
                "observed evidence or a concrete blocked result before review."
            ),
        }
        self._record_node_content_transcript(
            node,
            "TaskExecutor validation failed after retries; retrying the same "
            "active task instead of bypassing ResultReviewer into replan.",
        )
        terminal_nodes = [queued for queued in self.queue.items[1:] if queued.is_terminal]
        self.queue.clear_after_current()
        from tinycua.config.node_config import create_node_config
        from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
        from tinycua.loops.task_nodes import TinyCUATaskExecutorNode

        self.queue.items.extend(
            [
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )
        existing_terminal_ids = {
            queued.node_id for queued in self.queue.items if queued.is_terminal
        }
        for terminal in terminal_nodes:
            if terminal.node_id not in existing_terminal_ids:
                self.queue.items.append(terminal)
                existing_terminal_ids.add(terminal.node_id)
        return True

    def _successful_executor_action_results(
        self,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return successful non-state tool results that can guide continuation."""
        action_or_research_tools = {
            "write_file",
            "edit_file",
            "run_shell",
            "run_python",
            "fetch_url",
            "web_search",
        }
        useful = []
        for item in tool_results:
            if not isinstance(item, dict) or item.get("name") not in action_or_research_tools:
                continue
            output = item.get("output")
            if isinstance(output, dict) and output.get("success") is False:
                continue
            if isinstance(output, dict) and output.get("error"):
                continue
            useful.append(item)
        return useful

    def _validation_failure_content(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> str:
        """Build a visible failure response from runtime validation errors."""
        errors = "; ".join(validation.errors) or "unknown validation failure"
        return (
            f"TinyCUA could not complete the request because {node.node_id} "
            f"failed runtime validation: {errors}"
        )

    def _effective_max_attempts(self, node: Node) -> int:
        """Return bounded retry attempts for the loop-owned call path."""
        retry_policy = node.config.retry_policy
        if retry_policy.max_attempts is None:
            return _UNBOUNDED_RETRY_ATTEMPTS
        return max(retry_policy.max_attempts, 1)

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
        elif self._should_request_structured_tool_protocol(agent, node, resolved_tools):
            model_overrides["response_format"] = self._tool_protocol_response_format(
                node,
                resolved_tools
            )

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
        """Bound compact tool-decision nodes without constraining executors."""
        budget_by_node = {
            "query_analyst": 512,
            "digester": 768,
            "worker": 512,
            "task_create": 768,
            "task_analyzer": 1024,
            "task_assessor": 768,
            "result_reviewer": 768,
            "result_aggregation": 1536,
        }
        budget = budget_by_node.get(node.node_id)
        if budget is None:
            return None
        current = getattr(model, "max_tokens", None)
        if isinstance(current, int) and current <= budget:
            return None
        return budget

    def _should_request_structured_tool_protocol(
        self,
        agent: Agent,
        node: Node,
        resolved_tools: list[Tool],
    ) -> bool:
        """Return whether to force provider-side JSON tool-call grammar."""
        del agent, node, resolved_tools
        return False

    def _tool_protocol_response_format(
        self,
        node: Node,
        resolved_tools: list[Tool],
    ) -> dict[str, Any]:
        """Return JSON-schema response format for text-emitted tool calls."""
        protocol_tools = self._structured_tool_protocol_tools(node, resolved_tools)
        arguments_schema = self._structured_tool_arguments_schema(node, protocol_tools)
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "tinycua_tool_call_protocol",
                "strict": False,
                "schema": {
                    "type": "object",
                    "properties": {
                        "tool_calls": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "enum": [tool.name for tool in protocol_tools],
                                    },
                                    "arguments": arguments_schema,
                                },
                                "required": ["name", "arguments"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["tool_calls"],
                    "additionalProperties": False,
                },
            },
        }

    def _structured_tool_retry_message(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str:
        """Build a JSON-protocol retry instruction without prose framing."""
        protocol_tools = self._structured_tool_protocol_tools(node, resolved_tools)
        return (
            f"Retry attempt after validation failed: {error!s}. Your next "
            "response must be ONLY strict JSON matching the tool-call protocol: "
            '{"tool_calls":[{"name":"tool_name","arguments":{}}]}. '
            "Choose one or more valid tools and arguments from these available "
            f"tools: {', '.join(tool.name for tool in protocol_tools)}."
        )

    def _natural_retry_message(
        self,
        error: ValidationError,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str:
        """Build an assistant self-correction retry continuation."""
        del resolved_tools
        required = self._missing_or_required_tool_name(node, str(error))
        if required:
            return (
                f"I need to call {required} with the current evidence to finalize "
                f"the {node.node_id} step before proceeding."
            )
        return (
            f"I need to correct the {node.node_id} response based on the runtime "
            f"validation error before proceeding: {error!s}"
        )

    def _missing_or_required_tool_name(self, node: Node, error_text: str) -> str | None:
        """Return the most likely missing required tool for a retry message."""
        if node.node_id == "task_analyzer" and "task_decompose" in error_text:
            return "task_decompose"
        for tool_name in getattr(node.config.retry_policy, "required_tool_calls", []):
            if tool_name and tool_name in error_text:
                return str(tool_name)
        for tool_name in (
            "task_result_update",
            "task_review_decision",
            "task_update",
            "task_decompose",
            "task_init",
            "select_query_route",
            "select_worker_route",
        ):
            if tool_name in error_text:
                return tool_name
        return self._required_single_tool_choice_name(node)

    def _structured_tool_protocol_tools(
        self,
        node: Node,
        resolved_tools: list[Tool],
    ) -> list[Tool]:
        """Return tools eligible for provider-side JSON protocol selection."""
        required_route = self._required_single_tool_choice_name(node)
        preferred_names: set[str] | None = None
        if required_route is not None:
            preferred_names = {required_route}
        else:
            preferred_names = {
                "task_create": {"task_init"},
                "task_analyzer": {"task_decompose", "task_update"},
                "task_assessor": {"task_update"},
            }.get(node.node_id)
        if preferred_names is None:
            return resolved_tools
        preferred_tools = [tool for tool in resolved_tools if tool.name in preferred_names]
        return preferred_tools or resolved_tools

    def _structured_tool_arguments_schema(
        self,
        node: Node,
        protocol_tools: list[Tool],
    ) -> dict[str, Any]:
        """Return a JSON schema for protocol tool arguments when safe."""
        required_route = self._required_route_tool_name(node)
        if required_route is not None and hasattr(node, "classification_labels"):
            return {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "enum": list(getattr(node, "classification_labels", [])),
                    },
                    "reason": {"type": "string"},
                },
                "required": ["route"],
                "additionalProperties": False,
            }
        if len(protocol_tools) == 1:
            parameters = getattr(protocol_tools[0], "parameters", None)
            if isinstance(parameters, dict) and parameters.get("type") == "object":
                schema = dict(parameters)
                if schema.get("required") == []:
                    schema.pop("required")
                return schema
        return {"type": "object"}

    async def _invoke_agent_llm(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
        *,
        stream: bool = False,
    ) -> Any:
        """Invoke agent._call_llm while supporting async iterators in tests."""
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

    def _forced_tool_choice_for_node(
        self,
        agent: Agent,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str | dict[str, Any] | None:
        """Return provider-compatible forced tool_choice for tool-required nodes."""
        required = self._required_single_tool_choice_name(node)
        if required is None and self._requires_any_tool_choice(node):
            return "required" if resolved_tools else None
        if required is None:
            return None
        if required not in {tool.name for tool in resolved_tools}:
            return None
        model = getattr(agent, "llm_model", None)
        provider = getattr(model, "provider", "")
        if (
            self._required_route_tool_name(node) is not None
            and provider == "openai-chat-completions"
            and self._uses_local_openai_server(model)
        ):
            return "required"
        if provider == "openai-chat-completions" and not self._uses_local_openai_server(
            model
        ):
            return {"type": "function", "function": {"name": required}}
        return "required"

    def _requires_any_tool_choice(self, node: Node) -> bool:
        """Return whether a node must call some tool but not one fixed tool."""
        return node.node_id in {"task_executor", "result_reviewer"}

    def _llm_tools_for_required_choice(
        self,
        node: Node,
        resolved_tools: list[Tool],
        *,
        force_required_tool: bool,
    ) -> list[Tool]:
        """Restrict required singleton calls to the selected tool only."""
        required = self._required_single_tool_choice_name(node)
        if not force_required_tool:
            return resolved_tools
        if required is None:
            return resolved_tools
        route_tools = [tool for tool in resolved_tools if tool.name == required]
        return route_tools or resolved_tools

    def _validate_node_result(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate node output plus TinyCUA runtime invariants."""
        validation = node.validate_output(llm_result)
        for extra_validation in (
            self._validate_task_executor_action(node, llm_result),
            self._validate_tool_owned_task_state(node, llm_result),
            self._validate_result_reviewer_failed_approval(node, llm_result),
            self._validate_result_reviewer_inspection(node, llm_result),
            self._validate_final_response_content(node, llm_result),
        ):
            if not extra_validation.is_valid:
                validation.is_valid = False
                validation.errors.extend(extra_validation.errors)
        return validation

    def _validate_task_executor_repeated_missing_evidence(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Retry executor locally after repeated missing-evidence revisions."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "task_executor":
            return validation
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        for task_id in self._task_result_update_ids(tool_results):
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                continue
            if task.result is None:
                continue
            if "runtime_success_rejected" not in task.result.metadata:
                continue
            if not self._task_has_prior_missing_evidence_review(task):
                continue
            validation.is_valid = False
            validation.errors.append(
                "Repeated missing-evidence result after reviewer revision. First use "
                "write_file, edit_file, run_shell, or run_python to create or verify "
                "the required artifact before finalizing a successful result."
            )
            return validation
        return validation

    def _task_result_update_ids(
        self,
        tool_results: list[dict[str, Any]],
    ) -> list[str]:
        """Return task IDs mentioned by task_result_update tool outputs."""
        task_ids: list[str] = []
        for item in tool_results:
            if item.get("name") != "task_result_update":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("success") is not True:
                continue
            task_id = output.get("task_id")
            if isinstance(task_id, str):
                task_ids.append(task_id)
        return task_ids

    def _task_has_prior_missing_evidence_review(self, task: Any) -> bool:
        """Return whether reviewer already rejected missing implementation evidence."""
        for decision in task.reviewer_decisions:
            if not isinstance(decision, dict):
                continue
            if decision.get("decision") not in {"needs_revision", "rejected"}:
                continue
            rationale = str(decision.get("rationale", "")).lower()
            if (
                "evidence" in rationale
                or "artifact" in rationale
                or "write_file" in rationale
                or "implementation" in rationale
            ):
                return True
        return False

    def _validate_result_reviewer_failed_approval(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Prevent approval from accepting failed executor evidence as done."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "result_reviewer":
            return validation
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        for item in reversed(tool_results):
            if item.get("name") != "task_review_decision":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("decision") != "approved":
                return validation
            task_id = output.get("task_id")
            if not isinstance(task_id, str):
                return validation
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                return validation
            if task.result is None or task.result.success is not False:
                return validation
            validation.is_valid = False
            validation.errors.append(
                "ResultReviewer cannot approve a failed task result. Choose "
                "needs_revision, rejected, replan, or open_question after "
                "inspecting the failure evidence."
            )
            return validation
        return validation

    def _validate_result_reviewer_inspection(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Require artifact inspection before reviewer approval."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "result_reviewer":
            return validation
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        decision_result = None
        for item in reversed(tool_results):
            if item.get("name") == "task_review_decision":
                output = item.get("output")
                if isinstance(output, dict):
                    decision_result = output
                    break
        if not decision_result or decision_result.get("decision") != "approved":
            return validation
        task_id = decision_result.get("task_id")
        if not isinstance(task_id, str) or task_id not in self.root_session.task_store.tasks:
            return validation
        task = self.root_session.task_store.tasks[task_id]
        artifacts = list(task.artifacts)
        if task.result is not None:
            artifacts.extend(task.result.artifacts)
        if not artifacts:
            return validation
        inspected = any(
            item.get("name") in {"task_inspect", "list_files", "read_file"}
            and item.get("error") is None
            for item in tool_results
        )
        if inspected:
            return validation
        validation.is_valid = False
        validation.errors.append(
            "ResultReviewer must inspect relevant task context or artifact files "
            "with task_inspect, list_files, or read_file before approving tasks "
            "that produced artifacts."
        )
        return validation

    def _validate_final_response_content(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate that the terminal response is user-facing text."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "response":
            return validation
        content = llm_result.content.strip()
        if not content:
            validation.is_valid = False
            validation.errors.append("Final response must be non-empty.")
            return validation
        if '"tool_calls"' in content or "</tool_call>" in content:
            validation.is_valid = False
            validation.errors.append(
                "Final response must be natural user-facing text, not a tool-call "
                "protocol payload."
            )
        store = self.root_session.task_store
        if (
            store.root_task_id is not None
            and not store.all_done()
            and not self._allows_incomplete_task_terminal_response()
        ):
            validation.is_valid = False
            validation.errors.append(
                "Final response cannot synthesize success before every task in "
                "the worker task tree is actually completed. Failed tasks must "
                "be retried or locally replanned before terminal response."
            )
        return validation

    def _allows_incomplete_task_terminal_response(self) -> bool:
        """Return whether terminal response is an explicit open question."""
        for task in self.root_session.task_store.tasks.values():
            if task.metadata.get("open_question_reason"):
                return True
        return False

    def _can_stop_after_tool_batch(
        self,
        node: Node,
        llm_result: LLMResult,
        validation: ValidationResult,
    ) -> bool:
        """Return whether a tool batch completed this nonterminal node."""
        if node.is_terminal or not validation.is_valid:
            return False
        required_route = self._required_route_tool_name(node)
        if required_route is not None:
            return True
        if node.node_id == "digester":
            return self._tool_results_include(llm_result, "digest_information")
        if node.node_id in {
            "task_create",
            "task_analyzer",
            "task_assessor",
            "result_reviewer",
        }:
            return bool(llm_result.metadata.get("tool_results"))
        if node.node_id == "task_executor":
            return self._tool_results_include(llm_result, "task_result_update")
        return False

    def _tool_results_include(self, llm_result: LLMResult, tool_name: str) -> bool:
        """Return whether metadata contains a result for a named tool."""
        return any(
            isinstance(item, dict) and item.get("name") == tool_name
            for item in llm_result.metadata.get("tool_results", [])
        )

    def _validate_task_executor_action(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate that TaskExecutor performed work through tools."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "task_executor":
            return validation
        if llm_result.metadata.get("tool_results"):
            return validation
        validation.is_valid = False
        validation.errors.append(
            "TaskExecutor must use tools to execute, inspect, verify, record a "
            "result, or report a blocked state; do not return a plan-only answer."
        )
        return validation

    def _validate_task_executor_success_evidence(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Require concrete action evidence for successful executor results."""
        validation = ValidationResult(is_valid=True, errors=[])
        if node.node_id != "task_executor":
            return validation
        tool_results = [
            item for item in llm_result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ]
        successful_task_ids = self._successful_task_result_update_ids(tool_results)
        if not successful_task_ids:
            return validation
        evidence = [*tool_results, *self._stored_executor_partial_results(successful_task_ids)]
        if self._has_concrete_executor_action_evidence(evidence):
            return validation
        validation.is_valid = False
        validation.errors.append(
            "TaskExecutor success=True task_result_update requires concrete action "
            "evidence from write_file, edit_file, run_shell, or run_python. "
            "task_execute, prose/planning, and read/list-only evidence cannot prove "
            "successful implementation."
        )
        return validation

    def _successful_task_result_update_ids(
        self,
        tool_results: list[dict[str, Any]],
    ) -> list[str]:
        """Return task IDs whose persisted result is semantic success."""
        task_ids: list[str] = []
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
            if task.result is not None and task.result.success is True:
                task_ids.append(task_id)
        return task_ids

    def _stored_executor_partial_results(self, task_ids: list[str]) -> list[dict[str, Any]]:
        """Return previously observed executor evidence for task IDs."""
        stored: list[dict[str, Any]] = []
        for task_id in task_ids:
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                continue
            stored.extend(
                item for item in task.metadata.get("executor_partial_tool_results", [])
                if isinstance(item, dict)
            )
            if task.result is not None:
                stored.extend(
                    item for item in task.result.metadata.get("tool_results", [])
                    if isinstance(item, dict)
                )
        return stored

    def _has_concrete_executor_action_evidence(
        self,
        tool_results: list[dict[str, Any]],
    ) -> bool:
        """Return whether executor evidence includes successful implementation work."""
        concrete_action_tools = {"write_file", "edit_file", "run_shell", "run_python"}
        return any(
            item.get("name") in concrete_action_tools
            and self._tool_result_succeeded(item)
            for item in tool_results
        )

    def _tool_result_succeeded(self, item: dict[str, Any]) -> bool:
        """Return whether a tool result represents a successful operation."""
        if item.get("error"):
            return False
        output = item.get("output")
        if isinstance(output, dict):
            if output.get("success") is False:
                return False
            if output.get("error"):
                return False
            if output.get("timed_out") is True:
                return False
            exit_code = output.get("exit_code")
            if exit_code is not None and exit_code != 0:
                return False
        return True

    def _validate_tool_owned_task_state(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> ValidationResult:
        """Validate task-state nodes mutate state through tools, not prose."""
        validation = ValidationResult(is_valid=True, errors=[])
        tool_results = llm_result.metadata.get("tool_results", [])
        successful_tool_names = {
            str(item.get("name"))
            for item in tool_results
            if isinstance(item, dict)
            and isinstance(item.get("output"), dict)
            and item["output"].get("success") is True
        }
        required_by_node = {
            "task_create": {"task_init"},
            "task_executor": {"task_result_update"},
            "result_reviewer": {"task_review_decision"},
        }
        any_of_by_node = {
            "task_analyzer": {"task_decompose", "task_update"},
            "task_assessor": {"task_update"},
        }
        any_of = any_of_by_node.get(node.node_id)
        if any_of is not None:
            if successful_tool_names.intersection(any_of):
                return validation
            validation.is_valid = False
            validation.errors.append(
                f"{node.node_id} must call at least one successful "
                f"task-state tool from {sorted(any_of)}; task state cannot "
                "be inferred from prose."
            )
            return validation
        required = required_by_node.get(node.node_id)
        if node.node_id == "result_aggregation":
            store = self.root_session.task_store
            if store.root_task_id is not None and store.all_done():
                return validation
            validation.is_valid = False
            validation.errors.append(
                "result_aggregation requires an existing completed task tree; "
                "it cannot synthesize completion from missing task state."
            )
            return validation
        if required is None or required.issubset(successful_tool_names):
            return validation
        validation.is_valid = False
        validation.errors.append(
            f"{node.node_id} must call successful task-state tool(s): "
            f"{sorted(required)}. Task state cannot be inferred from prose."
        )
        return validation

    def _uses_local_openai_server(self, model: Any) -> bool:
        """Return whether the configured OpenAI-compatible server is local."""
        base_url = str(getattr(model, "base_url", "") or "")
        return any(host in base_url for host in ("localhost", "127.0.0.1", "0.0.0.0"))

    def _required_route_tool_name(self, node: Node) -> str | None:
        """Return the route-selection tool that must be called by a node."""
        required = list(getattr(node.config.retry_policy, "required_tool_calls", []))
        for tool_name in ("select_query_route", "select_worker_route"):
            if tool_name in required:
                return tool_name
        return None

    def _required_single_tool_choice_name(self, node: Node) -> str | None:
        """Return a singleton state/route tool that should be forced."""
        route_tool = self._required_route_tool_name(node)
        if route_tool is not None:
            return route_tool
        return {
            "task_create": "task_init",
            "task_assessor": "task_update",
        }.get(node.node_id)

    def _record_retry_continuation(
        self,
        node: Node,
        retry_message: str,
        attempt: int,
    ) -> None:
        """Record retry continuation in chat history without session_context reuse."""
        from tinycua.models.chat_record import ChatRecord

        self.root_session.chat_history.append(
            ChatRecord(
                role="assistant",
                record_type="retry",
                content=retry_message,
                visibility="internal",
                source_node_id=node.node_id,
                source_session_id=self.root_session.session_id,
                created_seq=len(self.root_session.chat_history),
                metadata={"attempt": attempt},
            )
        )

    def _normalize_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Ensure assistant tool calls have provider-compatible IDs and type."""
        normalized = []
        for index, tool_call in enumerate(tool_calls):
            item = dict(tool_call)
            function = dict(item.get("function") or {})
            name = function.get("name") or item.get("name") or f"tool_{index}"
            function.setdefault("name", name)
            function.setdefault("arguments", item.get("arguments") or "{}")
            item["function"] = function
            item["type"] = item.get("type") or "function"
            item["id"] = item.get("id") or f"call_{index}_{name}"
            normalized.append(item)
        return normalized

    def _coerce_structured_tool_calls(
        self,
        llm_result: LLMResult,
        resolved_tools: list[Tool],
    ) -> None:
        """Convert strict JSON tool-call protocol content into tool_calls.

        This is a provider-compatibility adapter, not a behavioral fallback: the
        LLM must explicitly select tool names and arguments in the documented
        JSON tool-call protocol. Arbitrary prose, labels, or partial JSON are
        ignored and remain validation failures.
        """
        if llm_result.tool_calls or not llm_result.content.strip():
            return
        allowed = {tool.name for tool in resolved_tools}
        parsed = self._parse_structured_tool_payload(llm_result.content, allowed)
        if parsed is None:
            return
        if not isinstance(parsed, dict) or not isinstance(parsed.get("tool_calls"), list):
            return
        tool_calls: list[dict[str, Any]] = []
        for index, item in enumerate(parsed["tool_calls"]):
            if not isinstance(item, dict):
                continue
            function = item.get("function") if isinstance(item.get("function"), dict) else {}
            name = item.get("name") or function.get("name")
            if not isinstance(name, str) or name not in allowed:
                continue
            arguments = item.get("arguments", function.get("arguments", {}))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments else {}
                except json.JSONDecodeError:
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                {
                    "id": item.get("id") or f"call_json_{index}_{name}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                }
            )
        if tool_calls:
            llm_result.tool_calls = tool_calls
            llm_result.metadata = dict(llm_result.metadata)
            llm_result.metadata["structured_tool_protocol"] = True

    def _parse_structured_tool_payload(
        self,
        content: str,
        allowed: set[str],
    ) -> dict[str, Any] | None:
        """Parse explicit tool JSON payloads without inferring from prose."""
        stripped = content.strip()
        try:
            parsed = json.loads(stripped, strict=False)
        except json.JSONDecodeError:
            parsed = None
        normalized = self._normalize_structured_tool_payload(parsed, allowed)
        if normalized is not None:
            return normalized

        tool_calls: list[dict[str, Any]] = []
        for candidate in self._json_object_candidates(stripped):
            try:
                parsed = json.loads(candidate, strict=False)
            except json.JSONDecodeError:
                continue
            normalized = self._normalize_structured_tool_payload(parsed, allowed)
            if normalized is None:
                continue
            candidate_calls = normalized.get("tool_calls")
            if not isinstance(candidate_calls, list):
                continue
            tool_calls.extend(
                item for item in candidate_calls
                if isinstance(item, dict)
            )
        if tool_calls:
            return {"tool_calls": tool_calls}
        return None

    def _json_object_candidates(self, content: str) -> list[str]:
        """Return balanced JSON-object substrings from provider wrapper text."""
        candidates: list[str] = []
        start: int | None = None
        depth = 0
        in_string = False
        escape = False
        for index, char in enumerate(content):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}" and depth:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(content[start : index + 1])
                    start = None
        return candidates

    def _normalize_structured_tool_payload(
        self,
        parsed: Any,
        allowed: set[str],
    ) -> dict[str, Any] | None:
        """Convert accepted explicit tool payload shapes to tool_calls shape."""
        if not isinstance(parsed, dict):
            return None
        if isinstance(parsed.get("tool_calls"), list):
            return parsed
        name = parsed.get("name")
        if isinstance(name, str) and name in allowed:
            arguments = parsed.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments, strict=False) if arguments else {}
                except json.JSONDecodeError:
                    return None
            if not isinstance(arguments, dict):
                return None
            return {"tool_calls": [{"name": name, "arguments": arguments}]}
        function = parsed.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str) and name in allowed:
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments, strict=False) if arguments else {}
                    except json.JSONDecodeError:
                        return None
                if not isinstance(arguments, dict):
                    return None
                return {"tool_calls": [{"name": name, "arguments": arguments}]}
        allowed_keys = [key for key in parsed if key in allowed]
        if len(allowed_keys) != 1:
            return None
        name = allowed_keys[0]
        arguments = parsed[name]
        if not isinstance(arguments, dict):
            return None
        return {"tool_calls": [{"name": name, "arguments": arguments}]}

    def _route_from_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        allowed_labels: list[str],
    ) -> str | None:
        """Extract a route label from route-selection tool calls."""
        classifier = RouteClassifier(allowed_labels)
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = function.get("name") or tool_call.get("name")
            if name not in {"select_query_route", "select_worker_route"}:
                continue
            arguments = function.get("arguments") or tool_call.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"route": arguments}
            if isinstance(arguments, dict) and "route" in arguments:
                return classifier.classify(str(arguments["route"]))
        return None

    def _build_on_complete_response(
        self,
        node: Node,
        llm_result: LLMResult,
    ) -> LLMResult | DecisionResult:
        """Build the response object passed to node completion hooks."""
        if not isinstance(node, DecisionNode):
            return llm_result
        tool_route = self._route_from_tool_calls(
            llm_result.tool_calls,
            node.classification_labels,
        )
        if tool_route is not None:
            return DecisionResult(
                route_label=tool_route,
                analysis_response=llm_result,
                classification_response=llm_result,
            )
        return DecisionResult(
            route_label="",
            analysis_response=llm_result,
            classification_response=llm_result,
        )

    def _trace_entry(
        self,
        node: Node,
        attempt: int,
        resolved_tools: list[Tool],
        on_complete_response: LLMResult | DecisionResult,
        llm_result: LLMResult | None = None,
    ) -> dict[str, Any]:
        """Build a trace entry with route, tool, and task-state evidence."""
        trace_entry = {
            "node_id": node.node_id,
            "node_type": type(node).__name__,
            "is_terminal": node.is_terminal,
            "attempt": attempt,
            "resolved_tool_names": [tool.name for tool in resolved_tools],
        }
        if isinstance(on_complete_response, DecisionResult):
            trace_entry["route_label"] = on_complete_response.route_label
            trace_entry["route_source"] = (
                "tool_call"
                if self._route_from_tool_calls(
                    on_complete_response.classification_response.tool_calls,
                    [on_complete_response.route_label],
                )
                else "missing_tool_call"
            )
        if llm_result is not None:
            if llm_result.content:
                trace_entry["llm_content"] = llm_result.content
            if llm_result.tool_calls:
                trace_entry["tool_calls"] = self._json_safe(llm_result.tool_calls)
        if llm_result is not None and llm_result.metadata.get("tool_results"):
            trace_entry["tool_results"] = llm_result.metadata["tool_results"]
        retry_exhaustion = getattr(node, "_last_retry_exhaustion", None)
        if retry_exhaustion is not None:
            trace_entry["retry_exhausted"] = True
            trace_entry["retry_exhaustion"] = self._json_safe(retry_exhaustion)
        task_state = self._task_state_snapshot()
        if task_state is not None:
            trace_entry["task_state"] = task_state
            trace_entry["task_tree"] = task_state
        return trace_entry

    def _apply_loop_result_hook(
        self,
        node: Node,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Run optional node-specific post-LLM parsing in loop path."""
        hook = getattr(node, "parse_loop_result", None)
        if hook is not None:
            hook(llm_result, node_input)

    def _publish_structured_outputs_to_root(self, node: Node) -> None:
        """Expose structured loop outputs on root session for observability."""
        from tinycua.models.digested_information import DigestedInformation

        if node.session is None:
            return
        for entry in node.session.session_context:
            if entry.segment != "output" or entry.source_node_id != node.node_id:
                continue
            if not isinstance(entry.content, DigestedInformation):
                continue
            if any(
                existing.record_id == entry.record_id
                for existing in self.root_session.session_context
            ):
                continue
            self.root_session.session_context.append(entry)

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
        resolved_tools: list[Tool],
        node_input: NodeInputLike | None = None,
        *,
        attempt: int = 1,
        retry_tool_results: list[dict[str, Any]] | None = None,
    ) -> tuple[str, ValidationResult, LLMResult]:
        """Finalize a streamed node: record output, fire lifecycle hooks.

        Args:
            node: The node that was streamed.
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
        collected_tool_calls = llm_result.tool_calls
        tool_results = self._execute_tool_calls(collected_tool_calls, resolved_tools)
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
        result_metadata = dict(llm_result.metadata)
        llm_result = self._record_node_output(node, combined, llm_result.tool_calls)
        llm_result.metadata.update(result_metadata)

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

        self._apply_loop_result_hook(node, llm_result, node_input)
        self._publish_structured_outputs_to_root(node)
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
        propagate_on_termination(
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

                # Advance queue (calls propagate on current node)
                self.queue.advance()
        finally:
            self._working_messages = all_messages

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
        self._inject_active_task_input(node)
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
        combined, tool_calls = self._execute_deterministic_node(node, resolved_tools)
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

            combined, validation, llm_result = self._finalize_streamed_node(
                node,
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
                )
                retry_feedback = self._tool_feedback_messages(llm_result)
                retry_tool_results = self._tool_results_from_llm_result(llm_result)
                self._record_retry_continuation(node, retry_message, attempt_number)

        async for event in self._stream_exhausted_node_events(
            node,
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
        if not self._route_task_executor_failure_to_reviewer(
            node,
            validation,
            llm_result,
        ):
            raise NodeExecutionError(self._validation_failure_content(node, validation))
        async for event in self._stream_node_completed(
            node,
            combined,
            emit_lifecycle,
            include_meta,
            final_only,
            node_type,
            max_attempts,
        ):
            yield event

    def _recover_task_assessor_validation_failure(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> bool:
        """Skip analyzer when assessor cannot select decomposition targets."""
        if node.node_id != "task_assessor" or self.queue.current is not node:
            return False
        if len(self.queue.items) > 1 and self.queue.items[1].node_id == "task_analyzer":
            del self.queue.items[1]
        root_id = self.root_session.task_store.root_task_id
        if root_id and root_id in self.root_session.task_store.tasks:
            self.root_session.task_store.tasks[root_id].metadata["assessor_recovery"] = {
                "source_node_id": node.node_id,
                "errors": list(validation.errors),
                "recovery": "skip_analyzer",
                "reason": (
                    "Assessor did not record selected decomposition targets; "
                    "continuing without analyzer for this assessment pass."
                ),
            }
        self._record_node_content_transcript(
            node,
            "TaskAssessor did not record decomposition targets; skipping the "
            "paired analyzer for this pass and continuing execution lifecycle.",
        )
        return True

    def _recover_task_analyzer_validation_failure(
        self,
        node: Node,
        validation: ValidationResult,
    ) -> bool:
        """Skip optional analyzer passes when the task tree can already execute."""
        if node.node_id != "task_analyzer" or self.queue.current is not node:
            return False
        root_id = self.root_session.task_store.root_task_id
        if root_id is None or root_id not in self.root_session.task_store.tasks:
            return False
        root = self.root_session.task_store.tasks[root_id]
        if not root.children:
            return False
        root.metadata["analyzer_recovery"] = {
            "source_node_id": node.node_id,
            "errors": list(validation.errors),
            "recovery": "skip_analyzer",
            "reason": (
                "Analyzer did not record additional decomposition or metadata; "
                "continuing with the existing task tree."
            ),
        }
        self._record_node_content_transcript(
            node,
            "TaskAnalyzer did not record additional task-state changes; "
            "continuing with the existing task tree.",
        )
        return True

    def _stream_retry_message(
        self,
        agent: Agent,
        node: Node,
        resolved_tools: list[Tool],
        error: ValidationError,
        attempt: int,
    ) -> str:
        """Build retry guidance for the canonical streaming path."""
        del agent, attempt
        return self._natural_retry_message(error, node, resolved_tools)

    def _append_tool_feedback_messages(
        self,
        messages: list[dict[str, Any]],
        llm_result: LLMResult,
    ) -> None:
        """Append assistant tool calls and tool results for streamed retries."""
        messages.extend(self._tool_feedback_messages(llm_result))

    def _tool_feedback_messages(self, llm_result: LLMResult) -> list[dict[str, Any]]:
        """Return latest tool-call feedback messages for a retry attempt."""
        tool_results = llm_result.metadata.get("tool_results", [])
        normalized_tool_calls = self._normalize_tool_calls(llm_result.tool_calls)
        if not normalized_tool_calls and not tool_results:
            return []
        messages: list[dict[str, Any]] = []
        if normalized_tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": llm_result.content,
                    "tool_calls": normalized_tool_calls,
                }
            )
        for index, tool_result in enumerate(tool_results):
            if not isinstance(tool_result, dict):
                continue
            tool_call = (
                normalized_tool_calls[index]
                if index < len(normalized_tool_calls)
                else {}
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id")
                    or str(tool_result.get("name", "")),
                    "name": str(tool_result.get("name", "")),
                    "content": json.dumps(tool_result, default=str),
                }
            )
        return messages

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
        stream_result = await self._call_agent_llm(
            agent,
            node,
            messages,
            resolved_tools,
            stream=True,
        )
        async for event in self._iter_stream_result_events(stream_result):
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

    def _execute_deterministic_node(
        self,
        node: Node,
        resolved_tools: list[Tool],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Execute a deterministic runtime node without an LLM call."""
        runner = getattr(node, "run_deterministic")
        llm_result = runner(self.queue)
        content = llm_result.content
        result_metadata = dict(llm_result.metadata)
        llm_result = self._record_node_output(node, content, llm_result.tool_calls)
        llm_result.metadata.update(result_metadata)
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
        propagate_on_termination(
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
        self._inject_active_task_input(node)

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
            return self._execute_deterministic_node(node, resolved_tools)

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
            if not self._route_task_executor_failure_to_reviewer(
                node,
                validation,
                llm_result,
            ):
                raise NodeExecutionError(self._validation_failure_content(node, validation))
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
            failure_content = self._validation_failure_content(node, validation)
            self._record_node_output(node, failure_content, [])
            self._record_node_content_transcript(node, failure_content)
            return failure_content, []
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
        propagate_on_termination(
            node.session or self.root_session,
            parent_session,
            self.root_session,
            rule,
        )

        return content, llm_result.tool_calls

    def _inject_active_task_input(self, node: Node) -> None:
        """Inject read-only active task context for TaskExecutor nodes."""
        if node.node_id != "task_executor" or self.queue.current is not node:
            return
        active = self.root_session.task_store.get_active_task()
        if active is None or node.node_id in self.queue._inputs:  # noqa: SLF001 - loop owns queue internals.
            return
        self.queue.set_input(
            node,
            [
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "active_task_id": active.task_id,
                            "active_task": self._json_safe(active.__dict__),
                            "task_tree": self._task_state_snapshot(),
                            "read_only": True,
                        },
                        default=str,
                    ),
                }
            ],
        )

    def _record_node_content_transcript(self, node: Node, content: str) -> None:
        """Record a bounded, deduplicated node transcript content event."""
        content = sanitize_internal_reprs(content)
        if not content.strip():
            return
        if not node.is_terminal:
            key = content.strip()
            if key in self._transcript_seen_node_contents:
                return
            self._transcript_seen_node_contents.add(key)
        if len(content) > 8_000:
            content = f"{content[:8_000]}…[truncated]"
        self._record_transcript_event(
            "transcript.node",
            self._node_label(node),
            content,
            node_id=node.node_id,
        )

    def _record_node_call_transcript(
        self,
        node: Node,
        messages: list[dict[str, Any]],
        resolved_tools: list[Tool],
    ) -> None:
        """Record full diagnostic input context for a node LLM call."""
        payload = {
            "phase": "llm_input",
            "tools": [tool.name for tool in resolved_tools],
            "messages": self._json_safe(messages),
        }
        self._record_transcript_event(
            "transcript.node_call",
            self._node_label(node),
            "LLM input " + json.dumps(payload, default=str),
            node_id=node.node_id,
        )

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
        node_input = None
        skip_record_ids: set[str] = set()
        if self.queue.current is node:
            node_input = self.queue.input_for_current()
            skip_record_ids = self._source_record_ids_from_node_input(node_input)

        # Build system message via SystemPromptBuilder
        builder = SystemPromptBuilder()
        instruction = node.build_instruction(override_instructions)
        if instruction:
            builder.add_static(instruction)

        system_msg = builder.build()
        if system_msg["content"]:
            messages.append(system_msg)

        # Add session context if policy says so
        context_session = node.session or self.root_session
        self._append_session_context_messages(
            messages,
            node,
            context_session,
            skip_record_ids,
        )

        # Add chat history if policy says so
        self._append_chat_history_messages(messages, node)

        # Add input context (merged SDK messages) as continuation
        self._append_input_context_messages(messages, node)

        self._append_node_input_messages(messages, node, node_input)

        continuation = node.build_continuation(context_session)
        if continuation.strip():
            self._append_nonblank_message(messages, "assistant", continuation)

        return messages

    def _append_session_context_messages(
        self,
        messages: list[dict[str, Any]],
        node: Node,
        context_session: Session,
        skip_record_ids: set[str],
    ) -> None:
        """Append reusable session context as assistant-role messages."""
        policy = node.config.message_policy
        if not policy.include_session_context or not context_session.session_context:
            return
        if policy.dedupe_by_origin_record_id:
            messages.extend(
                build_messages_with_dedupe(
                    context_session,
                    dedupe_by_origin_record_id=True,
                    skip_record_ids=skip_record_ids,
                )
            )
            return
        for entry in context_session.session_context:
            if self._session_entry_is_skipped(entry, skip_record_ids):
                continue
            content = (
                entry.get("content", "") if isinstance(entry, dict) else entry.content
            )
            self._append_nonblank_message(messages, "assistant", content)

    def _append_chat_history_messages(
        self,
        messages: list[dict[str, Any]],
        node: Node,
    ) -> None:
        """Append eligible chat-history messages for nodes that request them."""
        if not node.config.message_policy.include_chat_history:
            return
        for record in self.root_session.chat_history:
            if should_include_chat_record(record):
                self._append_nonblank_message(messages, record.role, record.content)

    def _append_input_context_messages(
        self,
        messages: list[dict[str, Any]],
        node: Node,
    ) -> None:
        """Append SDK/root input only for explicit entry-boundary nodes."""
        if not node.config.message_policy.include_input_context:
            return
        for message in self.root_session.input_context:
            self._append_nonblank_message(
                messages,
                message["role"],
                message["content"],
            )

    def _append_node_input_messages(
        self,
        messages: list[dict[str, Any]],
        node: Node,
        node_input: Any,
    ) -> None:
        """Append direct queue handoff messages for the active node."""
        if node_input is None:
            return
        try:
            for message in convert_node_input_to_messages(node_input):
                role = message.get("role", "assistant")
                if (
                    role == "user"
                    and not node.config.message_policy.include_input_context
                ):
                    role = "assistant"
                self._append_nonblank_message(
                    messages,
                    role,
                    message.get("content", ""),
                )
        except (TypeError, ValueError):
            logger.debug("node=%s invalid_node_input_ignored", node.node_id)

    def _source_record_ids_from_node_input(self, node_input: Any) -> set[str]:
        """Return source record IDs represented by direct node input."""
        metadata = getattr(node_input, "metadata", None)
        if not isinstance(metadata, dict):
            return set()
        record_ids = metadata.get("source_record_ids", [])
        if isinstance(record_ids, str):
            return {record_ids}
        if isinstance(record_ids, list):
            return {str(record_id) for record_id in record_ids}
        return set()

    def _session_entry_is_skipped(
        self,
        entry: Any,
        skip_record_ids: set[str],
    ) -> bool:
        """Return whether a session-context entry is already in NodeInput."""
        if not skip_record_ids or isinstance(entry, dict):
            return False
        return entry.record_id in skip_record_ids or (
            entry.origin_record_id is not None
            and entry.origin_record_id in skip_record_ids
        )

    def _append_nonblank_message(
        self,
        messages: list[dict[str, Any]],
        role: str,
        content: Any,
    ) -> None:
        """Append a message only when content is non-whitespace."""
        content = render_llm_content(content)
        if not content.strip():
            return
        key = (role, content)
        if any(
            existing.get("role") == key[0] and existing.get("content") == key[1]
            for existing in messages
        ):
            return
        messages.append({"role": role, "content": content})
