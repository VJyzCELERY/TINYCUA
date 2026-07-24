"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.agent.loop import BaseLoop

from tinycua.agent.tools.native.output_persist import (
    enforce_turn_budget,
    evict_superseded_file_reads,
    persist_if_oversized,
)
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops._loop_constants import (
    _MAX_PROVIDER_RETRIES,
    _MAX_TOOL_CONTINUATIONS,
    _UNBOUNDED_RETRY_ATTEMPTS,
)
from tinycua.loops.context_rendering import render_llm_content, sanitize_internal_reprs
from tinycua.loops.lazy_retry_mixin import LazyRetryMixin
from tinycua.loops.node_contract import LifecyclePhase, NodeState, phase_tool_names
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.orchestration_mixin import OrchestrationMixin
from tinycua.loops.prompt_protocol_mixin import PromptProtocolMixin
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.recovery_stages_mixin import RecoveryGuardMixin, RecoveryStagesMixin
from tinycua.loops.task_tree_rendering import render_task_tree
from tinycua.loops.trace_state_mixin import TraceStateMixin
from tinycua.loops.trace_state_mixin import normalize_tool_outcome
from tinycua.loops.validation_retry_mixin import ValidationRetryMixin
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.session import Session
from tinycua.models.session_context_entry import entry_content

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

    from tinycua.config.session_config import SessionConfig
    from tinycua.config.types import AgentMonitor
    from tinycua.loops.node import Node

logger = logging.getLogger(__name__)


# ponytail: per-tool rate-limit gate for shared backends. SearXNG's
# general-web engines (brave, google, startpage, duckduckgo) suspend under
# rapid-fire query load — experiment-2 fired ~30 searches in 5 minutes and
# brave/google hit rate-limit/CAPTCHA within 2 minutes, leaving only
# duckduckgo which returns 0 results for niche technical queries. A 3s
# minimum gap between web_search hits keeps the engines below their
# suspension thresholds. Map: tool name → (min_interval_s, last_call_ts).
# To add another throttled tool, add an entry here.
_TOOL_RATE_LIMITS: dict[str, tuple[float, float]] = {
    "web_search": (3.0, 0.0),
}

# Regex for inline reasoning blocks: <think>...</think>, <thinking>...</thinking>,
# <reasoning>...</reasoning> (case-insensitive, DOTALL for multiline blocks).
# Used as a fallback when the server doesn't split reasoning into a separate
# reasoning_content field (LM Studio without --reasoning-format deepseek).
# Qwen3 chat templates inject the opening <think> tag, so the model's output
# may contain only the closing </think> without an explicit opening — we handle
# both the full <think>...</think> and the bare </think> prefix cases.
_INLINE_THINK_RE = re.compile(
    r"<(?:think|thinking|reasoning)>(.*?)</(?:think|thinking|reasoning)>",
    re.DOTALL | re.IGNORECASE,
)
# Bare closing tag prefix: </think> ...rest (when the opening was injected by
# the chat template and the model only emits the close + visible answer).
_BARE_THINK_PREFIX_RE = re.compile(
    r"^(.*?)(?:</(?:think|thinking|reasoning)>)\s*",
    re.DOTALL | re.IGNORECASE,
)


def _extract_inline_thinking(content: str) -> tuple[str, str]:
    """Extract inline reasoning from content, return (reasoning, stripped_content).

    Handles two cases:
    1. Full <think>...</think> blocks anywhere in content.
    2. Bare </think> prefix (when the chat template injected the opening tag
       and the model only emitted the close + visible answer).

    Returns ("", content) when no reasoning is found.
    """
    if not content:
        return "", content
    reasoning_parts: list[str] = []
    # Case 1: full <think>...</think> blocks.
    def _capture(m: re.Match) -> str:
        reasoning_parts.append(m.group(1))
        return ""  # remove from content

    stripped = _INLINE_THINK_RE.sub(_capture, content)
    # Case 2: bare </think> prefix (reasoning before the close tag).
    if not reasoning_parts:
        m = _BARE_THINK_PREFIX_RE.match(stripped)
        if m and m.group(1).strip():
            reasoning_parts.append(m.group(1))
            stripped = stripped[m.end():]
    return ("\n".join(reasoning_parts).strip(), stripped.strip()) if reasoning_parts else ("", content)


def _detect_repetition(content: str, min_block: int = 50, threshold: int = 3) -> bool:
    """Detect if the model is in a degenerate repetition loop.

    Checks whether any substring of length >= ``min_block`` appears ``threshold``
    or more times in ``content``. Uses a simple approach: sample a few candidate
    substrings from different positions and count their occurrences. This is
    O(n * k) where k is the number of candidates — fast enough for periodic
    checks every ~20 deltas.

    Returns True if degenerate repetition is detected, False otherwise.
    Legitimate long generation (code, reports) rarely repeats the same 50-char
    block 3+ times verbatim, so false positives are unlikely.
    """
    if len(content) < min_block * threshold:
        return False
    # Sample candidate substrings from different positions in the content.
    # Take the first min_block chars, a chunk from the middle, and a chunk
    # near the end — if ANY of them appears threshold+ times, it's a loop.
    candidates: list[str] = []
    # Candidate 1: the very first block (catches "start repeating from beginning").
    candidates.append(content[:min_block])
    # Candidate 2: a block from the last quarter (catches "started repeating late").
    quarter = len(content) // 4
    if quarter + min_block <= len(content):
        candidates.append(content[quarter:quarter + min_block])
    # Candidate 3: the last min_block chars (catches "just started repeating").
    if len(content) >= min_block:
        candidates.append(content[-min_block:])
    for candidate in candidates:
        if not candidate.strip():
            continue
        # Count occurrences — use str.count which is C-level fast.
        # For non-overlapping counts this is sufficient; repetition loops
        # produce non-overlapping copies.
        count = content.count(candidate)
        if count >= threshold:
            return True
    return False


class TinyCUALoop(
    OrchestrationMixin,
    ValidationRetryMixin,
    LazyRetryMixin,
    RecoveryStagesMixin,
    RecoveryGuardMixin,
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
        # FR-060: re-entry signal — set by _unbounded_recovery when the
        # recovery budget is exhausted. Checked by callers to skip
        # on_complete/advance and re-dispatch the node with fresh context.
        self._recovery_reentry: bool = False
        self.workspace_dir = getattr(session_config, "workspace_dir", None)
        self.artifact_dir = getattr(session_config, "artifact_dir", None)
        self.session_dir = getattr(session_config, "session_dir", None)
        self._disable_tool_audit = getattr(session_config, "disable_tool_audit", False)
        self._tool_artifact_seq = 0
        self._pending_handoffs: list[NodeHandoff] = []
        self._resolved_tools_for_prompt: list[Tool] | None = None

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
                return render_llm_content(entry_content(entry))
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
            context_binder = getattr(tool, "bind_session_context", None)
            if callable(context_binder):
                context = [
                    {"role": message.get("role", "unknown"), "content": message.get("content", "")}
                    for message in self.root_session.input_context
                ]
                context.extend(
                    {
                        "role": entry.get("role", "unknown") if isinstance(entry, dict) else entry.role,
                        "content": entry_content(entry),
                        "segment": entry.get("segment") if isinstance(entry, dict) else entry.segment,
                        "source_node_id": entry.get("source_node_id") if isinstance(entry, dict) else entry.source_node_id,
                        "source_session_id": entry.get("source_session_id") if isinstance(entry, dict) else entry.source_session_id,
                    }
                    for entry in self.root_session.session_context
                )
                context.extend(
                    {
                        "role": record.role,
                        "content": record.content,
                        "record_type": record.record_type,
                        "source_node_id": record.source_node_id,
                        "source_session_id": record.source_session_id,
                    }
                    for record in self.root_session.chat_history
                    if record.record_type == "tool_result"
                )
                context_binder(
                    self.root_session.session_id,
                    context[-100:],
                )
            handoff_binder = getattr(tool, "bind_handoff_store", None)
            if callable(handoff_binder):
                handoff_binder(self._pending_handoffs)
            source_binder = getattr(tool, "bind_source_node", None)
            if callable(source_binder):
                source_binder(node.node_id)

    def _phase_tools(
        self,
        node: Node,
        tools: list[Tool],
        phase: LifecyclePhase,
    ) -> list[Tool]:
        """Resolve existing node tools for one focused lifecycle phase."""
        if phase == LifecyclePhase.TERMINATE and not self._can_terminate(node):
            phase = LifecyclePhase.COMMIT
        names = phase_tool_names(
            node.node_id, {tool.name for tool in tools}, phase
        )
        return [tool for tool in tools if tool.name in names]

    def _can_terminate(self, node: Node) -> bool:
        """Return whether the node's real commit state permits termination."""
        if not node.contract.is_satisfied(node.progress.satisfied_requirements):
            return False
        store = self.root_session.task_store
        if node.node_id == "task_create":
            return store.root_task_id is not None
        if node.node_id == "task_executor":
            active = store.get_active_task()
            return active is not None and active.result is not None
        if node.node_id == "result_reviewer":
            return store.active_task_id in store._staged_reviewer_decisions
        if node.node_id == "task_assessor":
            return any(handoff.source_node == node.node_id for handoff in self._pending_handoffs)
        return True

    def _attempt_tools(
        self,
        node: Node,
        resolved_tools: list[Tool],
        retry_message: str | None,
    ) -> list[Tool]:
        """Return tools for the current lifecycle phase or a normal retry."""
        if node.contract.requires_terminate:
            return self._phase_tools(
                node, resolved_tools, node.progress.lifecycle_phase
            )
        return self._tools_for_retry_attempt(node, resolved_tools, retry_message)

    @staticmethod
    def _advance_lifecycle_phase(node: Node, result: LLMResult) -> bool:
        """Advance a lifecycle node after its action summary or successful commit."""
        if not node.contract.requires_terminate:
            return False
        if node.progress.lifecycle_phase == LifecyclePhase.ACTION:
            node.progress.advance_lifecycle(LifecyclePhase.SUMMARY, result.content.strip())
            node.progress.advance_lifecycle(LifecyclePhase.COMMIT)
            return True
        if (
            node.progress.lifecycle_phase == LifecyclePhase.COMMIT
            and node.contract.is_satisfied(node.progress.satisfied_requirements)
        ):
            node.progress.advance_lifecycle(LifecyclePhase.TERMINATE)
            return True
        if node.progress.lifecycle_phase == LifecyclePhase.TERMINATE and any(
            item.get("name") == "terminate"
            and isinstance(item.get("output"), dict)
            and item["output"].get("success") is False
            for item in result.metadata.get("tool_results", [])
            if isinstance(item, dict)
        ):
            node.progress.advance_lifecycle(LifecyclePhase.COMMIT)
            return True
        return False

    @staticmethod
    def _lifecycle_phase_directive(node: Node) -> str:
        """Return explicit guidance for the node's newly entered phase."""
        if node.progress.lifecycle_phase == LifecyclePhase.COMMIT:
            return (
                "ACTION is complete. Prepare the required commit for this same "
                "assignment. Do not repeat action work or start another task."
            )
        if node.progress.lifecycle_phase == LifecyclePhase.TERMINATE:
            if node.node_id == "result_reviewer":
                return (
                    "Active-task decision is complete. Only now inspect unfinished "
                    "tasks and amend relevant descriptions or context with task_update. "
                    "This is context only. Do not review or execute those tasks, and do "
                    "not modify their artifacts. Then call terminate to return control "
                    "to the runtime."
                )
            return (
                "COMMIT succeeded. This node still owns only its current assignment. "
                "Do not repeat work or start another roadmap task. Call terminate now "
                "to return control to the runtime."
            )
        return "Continue only the current assigned lifecycle phase."

    def _append_lifecycle_phase_directive(
        self,
        messages: list[dict[str, Any]],
        node: Node,
        previous_phase: LifecyclePhase,
    ) -> None:
        """Append phase guidance only when a lifecycle transition occurred."""
        if node.progress.lifecycle_phase == previous_phase:
            return
        messages.append(
            {
                "role": "user",
                "content": f"[System: {self._lifecycle_phase_directive(node)}]",
            }
        )

    def _tools_for_lifecycle_result(
        self,
        node: Node,
        result: LLMResult,
        resolved_tools: list[Tool],
    ) -> list[Tool]:
        """Keep unavailable lifecycle calls confined to their current phase."""
        if not node.contract.requires_terminate:
            return resolved_tools
        return self._phase_tools(node, resolved_tools, node.progress.lifecycle_phase)

    def _advance_lifecycle_tools(
        self,
        node: Node,
        result: LLMResult,
        resolved_tools: list[Tool],
        current_tools: list[Tool],
    ) -> list[Tool]:
        """Switch to the next focused tool phase after a lifecycle transition."""
        if self._advance_lifecycle_phase(node, result):
            return self._tools_for_lifecycle_result(node, result, resolved_tools)
        return current_tools

    def _can_stop_tool_batch(
        self, node: Node, result: LLMResult, validation: ValidationResult
    ) -> bool:
        """Return whether a non-lifecycle node can finish after a tool batch."""
        return not node.contract.requires_terminate and self._can_stop_after_tool_batch(
            node, result, validation
        )

    async def _await_tool_rate_limit(self, tool_name: str) -> None:
        """Async sleep to enforce per-tool minimum call intervals.

        Used for shared backends (e.g. SearXNG) that suspend under
        rapid-fire load. See ``_TOOL_RATE_LIMITS``. No-op for unlisted
        tools.
        """
        entry = _TOOL_RATE_LIMITS.get(tool_name)
        if entry is None:
            return
        min_interval, last_ts = entry
        now = time.monotonic()
        wait = min_interval - (now - last_ts)
        if wait > 0:
            logger.debug(
                "tool_rate_limit name=%s wait=%.2fs",
                tool_name, wait,
            )
            await asyncio.sleep(wait)
        _TOOL_RATE_LIMITS[tool_name] = (min_interval, time.monotonic())

    async def _execute_tool_calls(
        self,
        agent: Agent,
        tool_calls: list[dict[str, Any]],
        resolved_tools: list[Tool],
    ) -> list[dict[str, Any]]:
        """Execute allowed tool calls against the active session state."""
        allowed_tools = {tool.name: tool for tool in resolved_tools}
        results: list[dict[str, Any]] = []
        terminate_seen = False
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = function.get("name") or tool_call.get("name")
            if not name:
                continue
            if name == "terminate":
                if terminate_seen:
                    continue
                terminate_seen = True
            call_id = str(tool_call.get("id") or "")

            def record(result: dict[str, Any]) -> None:
                result["call_id"] = call_id
                prompt_content = persist_if_oversized(
                    json.dumps(result, default=str), call_id or name, tool_name=name
                )
                result["prompt_content"] = prompt_content
                result["outcome"] = normalize_tool_outcome(
                    tool_call, result, content=prompt_content
                )
                self._record_tool_chat_result(result)
                results.append(result)

            if name not in allowed_tools:
                record(
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
                    record({"name": name, "allowed": True, "error": str(exc)})
                    continue
            if not isinstance(arguments, dict):
                record(
                    {"name": name, "allowed": True, "error": "arguments_not_object"}
                )
                continue
            arguments = self._normalize_tool_call_arguments(allowed_tools[name], arguments)
            self._log_tool_call_args(name, arguments)
            # ponytail: per-tool rate limit for shared backends. See
            # _TOOL_RATE_LIMITS. Async sleep so the event loop stays free.
            await self._await_tool_rate_limit(name)
            try:
                output = await ToolExecutor.execute(allowed_tools[name], arguments, agent)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001 - recorded for trace/debugging.
                record({"name": name, "allowed": True, "error": str(exc)})
                continue
            self._sync_root_task()
            tool_result = {"name": name, "allowed": True, "output": output}
            artifact_path = self._write_tool_audit_artifact(name, arguments, output)
            if artifact_path:
                tool_result["artifact_path"] = artifact_path
            record(tool_result)
        return results

    def _log_tool_call_args(self, name: str, arguments: dict[str, Any]) -> None:
        r"""Log a truncated preview of tool call arguments to stderr for debugging.

        File tools (str_replace, write_file, append_file) get path + content
        preview. Other tools get a truncated JSON preview. This makes it
        possible to diagnose issues like literal \n in content by inspecting
        the stderr log.
        """
        if name in {"str_replace", "write_file", "append_file"}:
            path = arguments.get("path", "?")
            if name == "str_replace":
                old = str(arguments.get("old_string", ""))[:100]
                new = str(arguments.get("new_string", ""))[:100]
                has_literal_n = "\\n" in str(arguments.get("new_string", ""))
                logger.debug(
                    "tool=%s path=%s old_string[:100]=%r new_string[:100]=%r%s",
                    name, path, old, new,
                    " [WARNING: literal \\n detected]" if has_literal_n else "",
                )
            else:
                content = str(arguments.get("content", ""))[:100]
                has_literal_n = "\\n" in str(arguments.get("content", ""))
                logger.debug(
                    "tool=%s path=%s content[:100]=%r%s",
                    name, path, content,
                    " [WARNING: literal \\n detected]" if has_literal_n else "",
                )
        else:
            # Truncated JSON preview for non-file tools.
            try:
                preview = json.dumps(arguments, default=str)[:200]
            except Exception:
                preview = str(arguments)[:200]
            logger.debug("tool=%s args=%s", name, preview)

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
        if self.artifact_dir is None or self._disable_tool_audit:
            return None
        if name not in {"run_shell", "run_python", "web_search", "fetch_url", "search_files"}:
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
            result = task.result
            partial_results = list(
                task.metadata.get("executor_partial_tool_results", [])
            )
            merged_tool_results = [*partial_results, *tool_results]
            evidence = self._json_safe(merged_tool_results)
            if result is not None:
                result.metadata["tool_results"] = evidence
                task.metadata.pop("executor_partial_tool_results", None)

    def _track_tool_calls_in_progress(
        self, node: Node, tool_results: list[dict[str, Any]]
    ) -> None:
        """Record visited + satisfied tools in node.progress (Milestone 2)."""
        for tr in tool_results:
            if isinstance(tr, dict) and tr.get("name"):
                prompt_content = tr.get("prompt_content")
                if not isinstance(prompt_content, str):
                    prompt_content = persist_if_oversized(
                        json.dumps(tr, default=str),
                        str(tr.get("call_id") or tr["name"]),
                        tool_name=str(tr["name"]),
                    )
                    tr["prompt_content"] = prompt_content
                    tr["outcome"] = normalize_tool_outcome(
                        {
                            "id": tr.get("call_id"),
                            "function": {"name": tr["name"]},
                        },
                        tr,
                        content=prompt_content,
                    )
                    self._record_tool_chat_result(tr)
                success = (
                    isinstance(tr.get("output"), dict)
                    and tr["output"].get("success") is not False
                )
                node.progress.mark_tool_called(tr["name"], success=success)
                outcome = tr.get("outcome")
                if isinstance(outcome, dict):
                    node.progress.correlated_outcomes.append(outcome)
                if success:
                    node.progress.accumulated_tool_results[str(tr["name"])] = tr

    def _track_input_tokens(self, node: Node, last_result: LLMResult) -> None:
        """Record the latest input-token count on the session for compaction triggers."""
        usage = last_result.metadata.get("usage") or {}
        if not isinstance(usage, dict):
            return
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        if isinstance(input_tokens, (int, float)):
            session = node.session or self.root_session
            session._last_input_tokens = int(input_tokens)

    def _agent_max_context(self, agent: Agent) -> int | None:
        """Return the bound model's max_context token limit, if available."""
        config = getattr(agent, "config", None)
        model = getattr(config, "llm_model", None)
        max_context = getattr(model, "max_context", None)
        return max_context if isinstance(max_context, (int, float)) else None

    def _build_compaction_llm_call(self, agent: Agent) -> Callable[[list[dict[str, str]]], Any]:
        """Build an async LLM callable for the compaction strategy.

        The callable takes a list of messages (system + user) and returns the
        assistant content string. Uses the same bound model as the worker so
        compaction doesn't require a separate client/credentials. Tool-less
        call (no tools passed) since compaction is pure summarization.
        """

        async def _llm_call(messages: list[dict[str, str]]) -> str:
            raw = await self._invoke_agent_llm(agent, messages, [], stream=False)
            content = raw.get("content", "") if isinstance(raw, dict) else ""
            return str(content).strip()

        return _llm_call

    async def _maybe_compact(self, node: Node, agent: Agent) -> None:
        """Compact session_context when the last LLM call neared the context window.

        Milestone 8 Stream B runtime trigger. Uses the provider-reported
        ``input_tokens`` from the previous call (stored on the session) and
        the bound model's ``max_context`` to decide if compaction is needed.
        When triggered, older ``session_context`` entries (all but the most
        recent ``compaction_keep_recent``) are summarized into one entry via
        the configured ``compaction_strategy``. Static context (mission,
        instruction, continuation) is never touched — only the audit trail.

        No-op when no strategy is configured, no token data is available, or
        the chicken-and-egg case (first call, no prior usage).
        """
        session = node.session or self.root_session
        sc = session.session_config
        if sc is None or sc.compaction_strategy is None:
            return
        # Lazy LLM-call wiring: if the strategy is a SimpleCompaction without
        # an llm_call, inject one built from the agent so compaction uses the
        # same model as the worker (not a hardcoded fallback). Set once.
        strategy = sc.compaction_strategy
        llm_call = getattr(strategy, "_llm_call", None)
        if llm_call is None and hasattr(strategy, "_llm_call"):
            strategy._llm_call = self._build_compaction_llm_call(agent)
        if session._last_input_tokens <= 0:
            return  # chicken-and-egg: no prior call data yet
        max_context = self._agent_max_context(agent)
        if not max_context or max_context <= 0:
            return
        threshold_tokens = int(sc.compaction_threshold * max_context)
        if session._last_input_tokens <= threshold_tokens:
            return
        keep_recent = max(0, sc.compaction_keep_recent)
        entries = list(session.session_context)
        if len(entries) <= keep_recent:
            return  # not enough to compact
        window = entries[:-keep_recent] if keep_recent else entries
        if not window:
            return
        logger.info(
            "compaction_trigger node=%s last_tokens=%d threshold=%d max_context=%s entries=%d keep_recent=%d",
            node.node_id,
            session._last_input_tokens,
            threshold_tokens,
            max_context,
            len(entries),
            keep_recent,
        )
        try:
            await session.compact_context(window=window)
        except Exception:
            logger.info("compaction_failed node=%s", node.node_id, exc_info=True)

    async def _force_compact(self, node: Node, agent: Agent) -> None:
        """Force-compact session_context regardless of token threshold (FR-086).

        Used when a provider error occurred (likely context overflow) — the
        failed call produced no usage data, so the normal threshold check in
        ``_maybe_compact`` can't fire. This bypasses the threshold and compacts
        whatever's compactable to shrink the prompt for the next retry.

        No-op when no strategy is configured or there aren't enough entries.
        Never raises — compaction failures are logged and swallowed.
        """
        session = node.session or self.root_session
        sc = session.session_config
        if sc is None or sc.compaction_strategy is None:
            return
        strategy = sc.compaction_strategy
        llm_call = getattr(strategy, "_llm_call", None)
        if llm_call is None and hasattr(strategy, "_llm_call"):
            strategy._llm_call = self._build_compaction_llm_call(agent)
        keep_recent = max(0, sc.compaction_keep_recent)
        entries = list(session.session_context)
        if len(entries) <= keep_recent:
            return
        window = entries[:-keep_recent] if keep_recent else entries
        if not window:
            return
        logger.info(
            "forced_compaction node=%s entries=%d keep_recent=%d",
            node.node_id, len(entries), keep_recent,
        )
        try:
            await session.compact_context(window=window)
        except Exception:
            logger.info("forced_compaction_failed node=%s", node.node_id, exc_info=True)

    def _append_tool_result_messages(
        self,
        attempt_messages: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        normalized_tool_calls: list[dict[str, Any]],
    ) -> None:
        """Append tool-result messages for the current tool batch.

        Persists oversized results to a temp file so the reviewer's
        attempt_messages don't balloon (experiment-4 peaked at 257K input
        tokens this way). Under the threshold this is a passthrough.
        """
        for index, tool_result in enumerate(tool_results):
            tool_call = (
                normalized_tool_calls[index]
                if index < len(normalized_tool_calls)
                else {}
            )
            raw_content = json.dumps(tool_result, default=str)
            tool_call_id = (
                tool_call.get("id") or tool_result.get("name", "")
            )
            tool_name = tool_result.get("name", "")
            content = tool_result.get("prompt_content")
            if not isinstance(content, str):
                content = persist_if_oversized(
                    raw_content, tool_call_id, tool_name=tool_name
                )
            attempt_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": content,
                }
            )

    async def _call_llm_with_provider_retry(
        self,
        agent: Agent,
        node: Node,
        attempt: int,
        attempt_messages: list[dict[str, Any]],
        attempt_tools: list[Tool],
        base_messages: list[dict[str, Any]],
        retry_feedback: list[dict[str, Any]],
        retry_message: str | None,
        provider_retries_ref: list[int],
        *,
        break_on_error: bool = False,
    ) -> dict[str, Any] | None:
        """Call the LLM with catch-compact-retry on provider errors (FR-086).

        Catches any non-cancel exception, force-compacts session_context, and
        retries with a smaller prompt. After ``_MAX_PROVIDER_RETRIES`` failed
        retries, re-raises the original exception.

        Args:
            agent: The SDK agent instance.
            node: The node being executed.
            attempt: The current attempt number (for logging).
            attempt_messages: The messages list for this attempt (rebuilt
                in-place after compaction when ``break_on_error`` is False).
            attempt_tools: The tools list for this attempt.
            base_messages: Base messages for rebuilding after compaction.
            retry_feedback: Retry feedback messages for rebuilding.
            retry_message: Retry message string for rebuilding.
            provider_retries_ref: A one-element list ``[count]`` acting as a
                mutable counter shared across call sites.
            break_on_error: When True (continuation rounds), force-compaction
                then return ``None`` to signal the caller to break to the
                next attempt. When False (initial call), retry in-place.

        Returns:
            The raw LLM response dict, or ``None`` when ``break_on_error`` is
            True and a provider error was caught (caller breaks to next
            attempt).

        Raises:
            The original exception after ``_MAX_PROVIDER_RETRIES`` retries.
        """
        while True:
            try:
                return await self._call_agent_llm(
                    agent, node, attempt_messages, attempt_tools,
                )
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as exc:
                provider_retries_ref[0] += 1
                if provider_retries_ref[0] > _MAX_PROVIDER_RETRIES:
                    raise
                suffix = ", aborting continuation" if break_on_error else ""
                logger.warning(
                    "provider_error_retry node=%s attempt=%d retry=%d error=%s — forcing compaction%s",
                    node.node_id, attempt, provider_retries_ref[0], str(exc)[:200], suffix,
                )
                await self._force_compact(node, agent)
                if break_on_error:
                    return None  # caller breaks to next attempt
                attempt_messages[:] = self._messages_with_retry_prompt(
                    base_messages, retry_feedback, retry_message,
                )

    def _reset_progress_for_retry(self, node: Node) -> None:
        """Reset node progress while retaining recovery evidence on re-entry."""
        if not self._recovery_reentry:
            node.progress.reset()
            return
        preserved = dict(node.progress.accumulated_tool_results)
        preserved_history = list(node.progress.stage_tool_history)
        recovery_attempts = dict(node.progress.recovery_attempts)
        recovery_fingerprint = node.progress.recovery_fingerprint
        recovery_escalations = list(node.progress.recovery_escalations)
        recovery_last_error = node.progress.recovery_last_error
        node.progress.reset()
        node.progress.accumulated_tool_results = preserved
        node.progress.stage_tool_history = preserved_history
        node.progress.recovery_attempts = recovery_attempts
        node.progress.recovery_fingerprint = recovery_fingerprint
        node.progress.recovery_escalations = recovery_escalations
        node.progress.recovery_last_error = recovery_last_error
        self._recovery_reentry = False

    def _record_attempt_tool_results(
        self,
        result: LLMResult,
        tool_results: list[dict[str, Any]],
        retry_tool_results: list[dict[str, Any]],
    ) -> None:
        """Attach accumulated tool results to the final attempt response."""
        if not tool_results:
            return
        result.metadata = dict(result.metadata)
        result.metadata["tool_results"] = list(tool_results)
        self._prepend_retry_tool_results(result, retry_tool_results)
        self._fill_content_from_recorded_task_result(result)

    async def _retry_invalid_attempt(
        self,
        node: Node,
        agent: Agent,
        resolved_tools: list[Tool],
        result: LLMResult,
        validation: ValidationResult,
        attempt: int,
        max_attempts: int,
        lazy_attempts: int,
    ) -> tuple[
        str,
        LLMResult,
        ValidationResult,
        int,
        tuple[str, list[dict[str, Any]], list[dict[str, Any]]] | None,
    ]:
        """Return the next retry action and optional standard retry context."""
        if attempt >= max_attempts:
            return "exhausted", result, validation, lazy_attempts, None
        retry_signal = await self._handle_retry_attempt(
            node, agent, resolved_tools, result, validation, attempt, lazy_attempts
        )
        if retry_signal is not None:
            action, result, validation, lazy_attempts = retry_signal
            return action, result, validation, lazy_attempts, None
        retry_context = self._prepare_standard_retry(
            node, resolved_tools, result, validation, attempt
        )
        return "retry", result, validation, lazy_attempts, retry_context

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
        lazy_attempts = 0  # FR-091: lazy retry counter; None doesn't burn a slot.
        self._reset_progress_for_retry(node)

        for attempt in range(1, max_attempts + 1):
            # Milestone 2: track per-node state transitions.
            node.progress.attempt_count = attempt
            node.progress.transition(
                NodeState.EXECUTING if attempt == 1 else NodeState.RETRYING,
                reason="attempt" if attempt == 1 else "retry",
            )
            # FR-086: per-attempt provider-error retry counter (mutable list
            # so the helper and continuation site share the same count).
            provider_retries_ref = [0]
            # FR-085: continuous monitoring — compact whenever the session
            # exceeds threshold, not just on retries. Runs on attempt 1 too,
            # as long as a prior call's usage data exists (chicken-and-egg
            # guard in _maybe_compact: _last_input_tokens <= 0 → skip).
            await self._maybe_compact(node, agent)
            attempt_messages = self._messages_with_retry_prompt(
                base_messages,
                retry_feedback,
                retry_message,
            )
            attempt_tools = self._attempt_tools(node, resolved_tools, retry_message)
            # FR-086: catch provider errors, force-compaction, and retry.
            raw_response = await self._call_llm_with_provider_retry(
                agent, node, attempt, attempt_messages, attempt_tools,
                base_messages, retry_feedback, retry_message,
                provider_retries_ref,
            )
            last_result = LLMResult(
                content=sanitize_internal_reprs(raw_response.get("content") or ""),
                role=raw_response.get("role", "assistant"),
                tool_calls=raw_response.get("tool_calls") or [],
                metadata=raw_response.get("metadata", {}),
                reasoning=raw_response.get("reasoning", ""),
            )
            # Milestone 8 Stream B: track token usage for compaction triggers.
            self._track_input_tokens(node, last_result)
            if not node.is_terminal and node.node_id != "result_aggregation":
                self._coerce_structured_tool_calls(last_result, attempt_tools)
            self._coerce_terminate_only_response(attempt_tools, last_result)
            attempt_tools = self._tools_for_lifecycle_result(
                node, last_result, resolved_tools
            )
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
                # Milestone 2: track visited + satisfied tools in node progress.
                self._track_tool_calls_in_progress(node, tool_results)
                self._enrich_task_results_from_tool_batch(node, all_tool_results)
                normalized_tool_calls = self._normalize_tool_calls(
                    last_result.tool_calls
                )
                last_result.tool_calls = normalized_tool_calls
                last_result.metadata = dict(last_result.metadata)
                last_result.metadata["tool_results"] = list(all_tool_results)
                self._prepend_retry_tool_results(last_result, retry_tool_results)
                self._fill_content_from_recorded_task_result(last_result)
                phase_before = node.progress.lifecycle_phase
                attempt_tools = self._advance_lifecycle_tools(
                    node, last_result, resolved_tools, attempt_tools
                )
                last_validation = self._validate_node_result(node, last_result)
                if self._can_stop_tool_batch(node, last_result, last_validation):
                    return last_result, attempt, last_validation
                if self._validation_needs_terminate(last_validation) or (
                    node.progress.lifecycle_phase == LifecyclePhase.TERMINATE
                    and any(
                        item.get("name") == "terminate"
                        and isinstance(item.get("output"), dict)
                        and item["output"].get("success") is True
                        for item in tool_results
                    )
                ):
                    break
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": last_result.content,
                    "tool_calls": normalized_tool_calls,
                }
                # Reasoning coherency: re-inject reasoning_content so the
                # model retains its thinking trace across tool-call turns
                # (Qwen3 maintainers: multi-step tool use requires it). Gated
                # on non-empty so non-reasoning models are unaffected.
                if last_result.reasoning:
                    assistant_msg["reasoning_content"] = last_result.reasoning
                attempt_messages.append(assistant_msg)
                self._append_tool_result_messages(attempt_messages, tool_results, normalized_tool_calls)
                self._append_lifecycle_phase_directive(
                    attempt_messages, node, phase_before
                )
                # Evict superseded file reads: when the model re-reads a file
                # it just edited, the older reads are stale (the file changed).
                # Stub them so the prompt stops growing from redundant re-reads
                # (experiment-4 executor re-read api.py 8× → ballooned to 68K).
                # This passes the FULL attempt_messages (assistant tool_calls +
                # tool results interleaved) so the path mapping can resolve.
                evict_superseded_file_reads(attempt_messages)
                # High safety-net ceiling only — NOT a tight budget. Normal
                # operation never hits it; it's an OOM guard for pathological
                # runaway (e.g. 100 distinct large file reads).
                enforce_turn_budget(attempt_messages)
                continuation_rounds += 1
                if continuation_rounds >= _MAX_TOOL_CONTINUATIONS:
                    break
                # FR-086: catch provider errors during continuation rounds
                # (context overflow from accumulated tool results). On error,
                # force-compaction and break to the next attempt.
                raw_response = await self._call_llm_with_provider_retry(
                    agent, node, attempt, attempt_messages, attempt_tools,
                    base_messages, retry_feedback, retry_message,
                    provider_retries_ref, break_on_error=True,
                )
                if raw_response is None:
                    break  # provider error → next attempt rebuilds from compacted context
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
                attempt_tools = self._tools_for_lifecycle_result(
                    node, last_result, resolved_tools
                )
            self._record_attempt_tool_results(
                last_result, all_tool_results, retry_tool_results
            )
            if self._advance_lifecycle_phase(node, last_result):
                retry_tool_results = self._tool_results_from_llm_result(last_result)
                retry_message = self._lifecycle_phase_directive(node)
                retry_feedback = self._tool_feedback_messages(last_result)
                continue
            last_validation = self._validate_node_result(node, last_result)
            if last_validation.is_valid:
                return last_result, attempt, last_validation
            action, last_result, last_validation, lazy_attempts, retry_context = (
                await self._retry_invalid_attempt(
                    node,
                    agent,
                    resolved_tools,
                    last_result,
                    last_validation,
                    attempt,
                    max_attempts,
                    lazy_attempts,
                )
            )
            if action == "return":
                return last_result, attempt, last_validation
            if action != "retry":
                break
            retry_message, retry_feedback, retry_tool_results = retry_context or (
                "",
                [],
                [],
            )

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
        response_format: dict[str, Any] | None = None,
    ) -> Any:
        """Call the SDK agent, optionally forcing a node-required route tool.

        The SDK reads ``tool_choice`` from the immutable ``LanguageModel``
        bound to the agent/client. TinyCUA keeps this reliability hook outside
        SDK source by temporarily swapping the model value and cached client for
        only this call, then restoring both immediately afterward.

        Args:
            agent: The SDK agent instance.
            node: The node being executed.
            messages: The message list for the LLM call.
            resolved_tools: Tools allowed for this node.
            stream: Whether to stream the response.
            force_required_tool: Whether to force tool_choice="required".
            response_format: Optional structured-output schema
                (``{"type": "json_schema", "schema": {...}}``). When set, the
                model is constrained to produce JSON (Milestone 3).
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
        if response_format is not None:
            model_overrides["response_format"] = response_format

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
        """Let the server decide max tokens — no client-side override.

        We do NOT hard-cap max_tokens: legitimate generation (long code files,
        detailed reports) may need many tokens, and capping would truncate
        real work. Instead, degenerate repetition is handled by the stream
        collector's repetition detection (same block repeating 3+ times →
        cut the stream), which is surgical and doesn't affect normal generation.
        """
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
        reasoning_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        async for event in stream_result:
            event_type = event.get("type") if isinstance(event, dict) else None
            if event_type == "response.output_text.delta":
                content_parts.append(str(event.get("delta", "")))
            elif event_type == "response.reasoning.delta":
                # Reasoning model coherency (Qwen3/DeepSeek/etc.): accumulate
                # the thinking trace so it can be re-injected as
                # reasoning_content on the next turn's assistant message.
                reasoning_parts.append(str(event.get("delta", "")))
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
        result = {
            "role": "assistant",
            "content": "".join(content_parts),
            "tool_calls": tool_calls,
            "metadata": metadata,
        }
        reasoning_text = "".join(reasoning_parts)
        # Inline-tag fallback: when the server doesn't split reasoning into a
        # separate field (LM Studio without --reasoning-format deepseek), Qwen3
        # emits ... inline in content. Extract it so it doesn't leak into the
        # next turn's content verbatim (inflating context + confusing the model).
        content_text = result["content"]
        if not reasoning_text and content_text:
            extracted, stripped = _extract_inline_thinking(content_text)
            if extracted:
                reasoning_text = extracted
                result["content"] = stripped
        if reasoning_text:
            result["reasoning"] = reasoning_text
        return result

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
        """Collect provider stream events and yield policy-filtered events.

        Includes two hallucination/degeneration guards (no LLM needed — pure
        algorithmic, instant, deterministic):

        1. Repetition detection: if a substring of >= 50 chars appears 3+ times
           in the accumulated content, the model is in a degenerate loop — cut
           the stream. Catches the "Inspect the root goal..." pattern from
           experiment-4 (same ~200-char block repeated 22K tokens).

        2. Time watchdog: if the stream has been running for > 120s without
           producing a tool call or finishing, cut it. Catches stuck states
           that aren't simple repetition (infinite reasoning, network stall).

        Neither hard-caps max_tokens — legitimate long generation is unaffected
        because real content doesn't repeat the same 50-char block 3+ times.
        """
        import time as _time

        # ponytail: LM Studio can ignore forced single-tool calls while streaming;
        # terminate has no user-visible text, so use non-stream for that retry.
        stream = [tool.name for tool in resolved_tools] != ["terminate"]
        if node.contract.requires_terminate:
            stream_result = await BaseLoop(max_iterations=_UNBOUNDED_RETRY_ATTEMPTS).run(
                agent, messages, resolved_tools, stream=True
            )
        else:
            stream_result = await self._call_agent_llm(
                agent,
                node,
                messages,
                resolved_tools,
                stream=stream,
            )
        _rep_check_interval = 20   # check every N deltas (avoid per-delta cost)
        _rep_min_block = 50        # min substring length to consider a repeat
        _rep_threshold = 3         # N occurrences of the same substring → cut
        _rep_max_content = 20_000  # don't scan beyond this (cap CPU)
        _watchdog_seconds = 120     # max seconds per LLM call without tool/finish
        _delta_count = 0
        _stream_start = _time.monotonic()
        async for event in self._iter_stream_result_events(stream_result):
            event_type = event.get("type", "")
            # Time watchdog — cut if stuck for too long.
            if _time.monotonic() - _stream_start > _watchdog_seconds:
                break
            if event_type == "response.output_text.delta":
                delta_text = str(event.get("delta", ""))
                if node.is_terminal:
                    content_parts.append(delta_text)
                    continue
                _delta_count += 1
                transcript = self._handle_stream_event(
                    node,
                    event,
                    content_parts,
                    collected_tool_calls,
                )
                # Periodically check for degenerate repetition.
                if _delta_count % _rep_check_interval == 0:
                    full_content = "".join(content_parts)
                    if len(full_content) > _rep_max_content:
                        full_content = full_content[-_rep_max_content:]
                    if _detect_repetition(full_content, _rep_min_block, _rep_threshold):
                        break
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
                continue
            # Non-delta events
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
        self._mark_successful_termination(node, resolved_tools)

    @staticmethod
    def _mark_successful_termination(node: Node, tools: list[Tool]) -> None:
        """Record a successful terminate call executed inside the SDK loop."""
        for tool in tools:
            result = getattr(tool, "last_result", None)
            if (
                tool.name == "terminate"
                and isinstance(result, dict)
                and result.get("success") is True
            ):
                node.progress.mark_tool_called("terminate")
                return

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
