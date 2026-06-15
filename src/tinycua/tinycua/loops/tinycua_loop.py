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
    should_include_chat_record,
)
from tinycua.loops.node import DecisionNode, DecisionResult, build_messages_with_dedupe
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
        queue_factory: Callable[[], NodeQueue] | None = None,
    ) -> None:
        """Initialize TinyCUALoop.

        Args:
            root_session: The root session for this loop. Created if not provided.
            queue: Node queue for execution. Created if not provided.
            session_config: Session configuration to apply.
            max_iterations: Maximum loop iterations before forced stop.
            default_terminal_node: Default terminal node for ensure_terminal() bootstrap.
            agent_monitor: Optional agent-level monitor hook for observing node execution.
            queue_factory: Optional factory used to create a fresh run queue per call.
        """
        super().__init__(max_iterations=max_iterations)
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

    def _fallback_terminal_content(self) -> str:
        """Build a deterministic non-empty terminal fallback response."""
        for message in reversed(self.root_session.input_context):
            if message.get("role") == "user" and str(message.get("content", "")).strip():
                return f"Processed request: {message['content']}"
        return "Processed request."

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
            self.default_terminal_node = self.queue.items[-1] if self.queue.items else None

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
            if (
                node.is_terminal
                and not content.strip()
                and self._synthetic_terminal_fallback_enabled()
            ):
                content = self._fallback_terminal_content()
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
            if node.is_terminal and self.queue.current is node:
                self._final_response_events = [
                    {
                        "type": "response.output_text.done",
                        "content": content,
                        "node_id": node.node_id,
                    }
                ]
                break
            if node.is_terminal:
                continue

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
        route_refresher = getattr(node, "refresh_route_options", None)
        if callable(route_refresher):
            route_refresher()
        messages = self._build_node_messages(node, override_instructions)
        resolved_tools = node.config.tool_policy.resolve_tools(tools)
        self._bind_session_tools(resolved_tools)
        return messages, resolved_tools

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

    def _synthetic_terminal_fallback_enabled(self) -> bool:
        """Return whether empty terminal content should be filled synthetically."""
        return bool(
            getattr(self.session_config, "allow_synthetic_terminal_fallback", False)
        )

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
                results.append({"name": name, "allowed": False, "error": "tool_not_allowed"})
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
                results.append({"name": name, "allowed": True, "error": "arguments_not_object"})
                continue
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

    def _node_label(self, node: Node) -> str:
        """Return a compact human-readable node label."""
        label = type(node).__name__
        for prefix in ("TinyCUA",):
            if label.startswith(prefix):
                label = label[len(prefix):]
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

    def _latest_user_query(self) -> str:
        """Return the latest user prompt in the root input context."""
        for message in reversed(self.root_session.input_context):
            if message.get("role") == "user":
                return str(message.get("content", "")).strip()
        return "TinyCUA task"

    def _apply_task_lifecycle_marker(self, node: Node, content: str) -> None:
        """Record deterministic task lifecycle state for task-route nodes."""
        from tinycua.models.task import TaskResult, TaskStatus

        store = self.root_session.task_store
        if node.node_id == "task_create" and store.root_task_id is None:
            store.create_task(self._latest_user_query() or "TinyCUA task", description=content)
        elif node.node_id == "task_analyzer" and store.root_task_id is not None:
            root = store.tasks[store.root_task_id]
            root.metadata["analyzed"] = "true"
        elif node.node_id == "analysis_effort" and store.root_task_id is not None:
            root = store.tasks[store.root_task_id]
            root.metadata["analysis_effort"] = content or "standard"
        elif node.node_id == "task_assessor" and store.root_task_id is not None:
            root = store.tasks[store.root_task_id]
            root.metadata["assessed"] = "true"
        elif node.node_id == "task_executor" and store.root_task_id is not None:
            root = store.tasks[store.root_task_id]
            if root.status != TaskStatus.COMPLETED:
                root.status = TaskStatus.IN_PROGRESS
        elif node.node_id == "result_reviewer" and store.root_task_id is not None:
            root = store.tasks[store.root_task_id]
            root.metadata["reviewed"] = "true"
        elif node.node_id == "result_aggregation" and store.root_task_id is not None:
            root = store.tasks[store.root_task_id]
            root.result = TaskResult(content=content or "Aggregated worker result")
            root.status = TaskStatus.COMPLETED
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

        for attempt in range(1, max_attempts + 1):
            raw_response = await self._call_agent_llm(
                agent,
                node,
                messages,
                resolved_tools,
            )
            last_result = LLMResult(
                content=raw_response.get("content") or "",
                role=raw_response.get("role", "assistant"),
                tool_calls=raw_response.get("tool_calls") or [],
                metadata=raw_response.get("metadata", {}),
            )
            tool_results = self._execute_tool_calls(last_result.tool_calls, resolved_tools)
            if tool_results:
                normalized_tool_calls = self._normalize_tool_calls(last_result.tool_calls)
                last_result.tool_calls = normalized_tool_calls
                last_result.metadata = dict(last_result.metadata)
                last_result.metadata["tool_results"] = tool_results
                messages.append(
                    {
                        "role": "assistant",
                        "content": last_result.content,
                        "tool_calls": normalized_tool_calls,
                    }
                )
                for index, tool_result in enumerate(tool_results):
                    tool_call = normalized_tool_calls[index] if index < len(normalized_tool_calls) else {}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id") or tool_result.get("name", ""),
                            "name": tool_result.get("name", ""),
                            "content": json.dumps(tool_result, default=str),
                        }
                    )
                raw_response = await self._call_agent_llm(
                    agent,
                    node,
                    messages,
                    resolved_tools,
                    force_required_tool=False,
                )
                last_result = LLMResult(
                    content=raw_response.get("content") or "",
                    role=raw_response.get("role", "assistant"),
                    tool_calls=raw_response.get("tool_calls") or [],
                    metadata={
                        **raw_response.get("metadata", {}),
                        "tool_results": tool_results,
                    },
                )
            last_validation = node.validate_output(last_result)
            if last_validation.is_valid:
                return last_result, attempt, last_validation
            if attempt < max_attempts:
                error = ValidationError("; ".join(last_validation.errors))
                retry_message = node._build_retry_text(error, attempt)
                self._record_retry_continuation(node, retry_message, attempt)
                messages.append(
                    {
                        "role": "assistant",
                        "content": retry_message,
                    }
                )

        node._handle_exhaustion(last_validation, max_attempts)
        return last_result, max_attempts, last_validation

    def _effective_max_attempts(self, node: Node) -> int:
        """Return bounded retry attempts for the loop-owned call path."""
        retry_policy = node.config.retry_policy
        if self._required_route_tool_name(node) is not None:
            return 1
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
        if tool_choice is None:
            return await self._invoke_agent_llm(
                agent,
                messages,
                llm_tools,
                stream=stream,
            )

        config = getattr(agent, "config", None)
        model = getattr(config, "llm_model", None)
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
        config.llm_model = model.model_copy(update={"tool_choice": tool_choice})
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
            return await result
        return result

    def _forced_tool_choice_for_node(
        self,
        agent: Agent,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str | dict[str, Any] | None:
        """Return provider-compatible forced tool_choice for route nodes."""
        required = self._required_route_tool_name(node)
        if required is None:
            return None
        if required not in {tool.name for tool in resolved_tools}:
            return None
        model = getattr(agent, "llm_model", None)
        provider = getattr(model, "provider", "")
        if provider == "openai-chat-completions" and not self._uses_local_openai_server(model):
            return {"type": "function", "function": {"name": required}}
        return "required"

    def _llm_tools_for_required_choice(
        self,
        node: Node,
        resolved_tools: list[Tool],
        *,
        force_required_tool: bool,
    ) -> list[Tool]:
        """Restrict required route calls to the route tool only."""
        required = self._required_route_tool_name(node)
        if not force_required_tool or required is None:
            return resolved_tools
        route_tools = [tool for tool in resolved_tools if tool.name == required]
        return route_tools or resolved_tools

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

    def _decision_fallback_label(self, node: DecisionNode) -> str | None:
        """Return configured fallback route for invalid decision responses."""
        if isinstance(node, TinyCUAQueryAnalystNode):
            policy = getattr(self.session_config, "interaction_policy", None)
            strategy = getattr(policy, "uncertain_strategy", "fallback_response")
            if strategy == "route_worker":
                return "worker"
            if strategy == "fail":
                return None
            return "passthrough"
        return node.classification_labels[0] if node.classification_labels else None

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
        fallback_label = self._decision_fallback_label(node)
        route_label = RouteClassifier(
            node.classification_labels,
            fallback_label=fallback_label,
        ).classify(llm_result.content)
        return DecisionResult(
            route_label=route_label,
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
                else "content_or_fallback"
            )
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
    ) -> str:
        """Finalize a streamed node: record output, fire lifecycle hooks.

        Args:
            node: The node that was streamed.
            content_parts: Accumulated text delta parts.
            collected_tool_calls: Collected tool call events.
            resolved_tools: Tools allowed for the streamed node.

        Returns:
            The combined content string.
        """
        combined = "".join(content_parts)
        tool_results = self._execute_tool_calls(collected_tool_calls, resolved_tools)
        llm_result = self._record_node_output(node, combined, collected_tool_calls)
        if tool_results:
            llm_result.metadata["tool_results"] = tool_results

        self._apply_loop_result_hook(node, llm_result, None)
        self._publish_structured_outputs_to_root(node)
        self._apply_task_lifecycle_marker(node, combined)
        on_complete_response = self._build_on_complete_response(node, llm_result)
        node.on_complete(self.queue, on_complete_response)

        trace_entry = self._trace_entry(
            node,
            1,
            node.config.tool_policy.resolve_tools([]),
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

        return combined

    async def _run_stream(  # noqa: C901 — streaming lifecycle complexity is inherent
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
        self._usage_events = []
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
                    stream_result = await self._call_agent_llm(
                        agent,
                        node,
                        messages,
                        resolved_tools,
                        stream=True,
                    )
                    async for event in stream_result:  # type: ignore[union-attr]
                        event_type = event.get("type")
                        if event_type == "response.output_text.delta":
                            delta = event.get("delta", "")
                            content_parts.append(delta)
                            transcript = self._record_transcript_event(
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
                        if is_terminal_node and event_type == "response.output_text.delta":
                            self._final_response_events.append(dict(event))
                        enriched = self._enrich_and_yield(
                            event,
                            include_meta,
                            node.node_id,
                            node_type,
                            attempt,
                        )
                        if not final_only or is_terminal_node:
                            yield enriched
                            if event_type == "response.output_text.delta":
                                yield transcript
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
                    resolved_tools,
                )
                if (
                    node.is_terminal
                    and not combined.strip()
                    and self._synthetic_terminal_fallback_enabled()
                ):
                    combined = self._fallback_terminal_content()

                # Record assistant response in working messages
                if combined:
                    all_messages.append({"role": "assistant", "content": combined})

                # Record tool calls in working messages for transcript completeness
                for tool_call in collected_tool_calls:
                    all_messages.append({
                        "role": "assistant",
                        "tool_calls": [tool_call],
                    })

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

        llm_result, attempt, validation = await self._call_node_with_retry(
            node,
            agent,
            messages,
            resolved_tools,
        )
        content = llm_result.content
        result_metadata = dict(llm_result.metadata)
        llm_result = self._record_node_output(node, content, llm_result.tool_calls)
        llm_result.metadata.update(result_metadata)
        if content:
            self._record_transcript_event(
                "transcript.node",
                self._node_label(node),
                content,
                node_id=node.node_id,
            )
        for tool_result in llm_result.metadata.get("tool_results", []):
            self._record_transcript_event(
                "transcript.tool_result",
                self._node_label(node),
                json.dumps(tool_result, default=str),
                node_id=node.node_id,
                tool_name=str(tool_result.get("name", "tool")),
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
                            "read_only": True,
                        },
                        default=str,
                    ),
                }
            ],
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
        if node.config.message_policy.include_session_context and context_session.session_context:
            dedupe = node.config.message_policy.dedupe_by_origin_record_id
            if dedupe:
                messages.extend(
                    build_messages_with_dedupe(
                        context_session, dedupe_by_origin_record_id=True
                    )
                )
            else:
                for m in context_session.session_context:
                    if isinstance(m, dict):
                        self._append_nonblank_message(
                            messages,
                            m.get("role", "user"),
                            m.get("content", ""),
                        )
                    else:
                        self._append_nonblank_message(messages, m.role, m.content)

        # Add chat history if policy says so
        if (
            node.config.message_policy.include_chat_history
            and self.root_session.chat_history
        ):
            for m in self.root_session.chat_history:
                if should_include_chat_record(m):
                    self._append_nonblank_message(messages, m.role, m.content)

        # Add input context (merged SDK messages) as continuation
        if self.root_session.input_context:
            for m in self.root_session.input_context:
                self._append_nonblank_message(messages, m["role"], m["content"])

        if self.queue.current is node:
            node_input = self.queue.input_for_current()
            try:
                for message in convert_node_input_to_messages(node_input):
                    self._append_nonblank_message(
                        messages,
                        message.get("role", "user"),
                        message.get("content", ""),
                    )
            except (TypeError, ValueError):
                logger.debug("node=%s invalid_node_input_ignored", node.node_id)

        return messages

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
        messages.append({"role": role, "content": content})
