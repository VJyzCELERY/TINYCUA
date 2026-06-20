"""Trace/state recording mixin for TinyCUALoop.

Extracted from ``tinycua_loop.py`` to keep the core loop file under 1000 LOC.
All methods are ``self.``-bound and resolved at runtime via MRO when
``TinyCUALoop`` inherits this mixin alongside the other mixins and ``BaseLoop``.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult
from tinycua.loops.context_rendering import looks_like_planner_prose, sanitize_internal_reprs
from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.loops.route_classifier import RouteClassifier
from tinycua.models.stream_event import enrich_stream_event, make_lifecycle_event

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)

class TraceStateMixin:
    """Mixin extracted from TinyCUALoop for modularity."""

    def _artifacts_from_tool_results(
        self,
        tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract durable artifact references from tool execution results."""
        artifacts: list[dict[str, Any]] = []
        for item in tool_results:
            name = item.get("name")
            # File path artifacts from write_file / edit_file
            if name in {"write_file", "str_replace", "append_file"}:
                output = item.get("output")
                if isinstance(output, dict) and output.get("success") is True and output.get("path"):
                    artifacts.append(
                        {
                            "path": str(output["path"]),
                            "kind": "file",
                            "metadata": {"tool_name": name},
                        }
                    )
            # Audit artifact from action/research tools
            artifact_path = item.get("artifact_path")
            if artifact_path:
                artifacts.append(
                    {
                        "path": str(artifact_path),
                        "kind": "tool_audit",
                        "metadata": {"tool_name": name},
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

    def _successful_executor_action_results(
        self, tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return successful non-state tool results that can guide continuation."""
        action_or_research_tools = {
            "write_file", "str_replace", "append_file", "run_shell", "run_python",
            "fetch_url", "web_search",
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
            if isinstance(output, dict) and output.get("timed_out") is True:
                continue
            if isinstance(output, dict) and output.get("exit_code") not in (None, 0):
                continue
            useful.append(item)
        return useful

    def _successful_executor_inspection_results(
        self, tool_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return successful read-only executor evidence usable for retry."""
        useful = []
        for item in tool_results:
            if not isinstance(item, dict) or item.get("allowed") is False:
                continue
            if item.get("name") not in {"read_file", "list_files", "task_inspect", "search_files"}:
                continue
            output = item.get("output")
            if isinstance(output, dict) and (
                output.get("success") is False or output.get("error")
            ):
                continue
            useful.append(item)
        return useful

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
                try:
                    return classifier.classify(str(arguments["route"]))
                except ValueError:
                    return None
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

    def _record_node_content_transcript(self, node: Node, content: str) -> None:
        """Record a bounded, deduplicated node transcript content event."""
        content = sanitize_internal_reprs(content)
        if not content.strip():
            return
        if not node.is_terminal and looks_like_planner_prose(content):
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
