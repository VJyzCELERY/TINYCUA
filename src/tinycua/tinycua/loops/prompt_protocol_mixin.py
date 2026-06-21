"""Prompt building and tool protocol mixin for TinyCUALoop.

Extracted from ``tinycua_loop.py`` to keep the core loop file under 1000 LOC.
All methods are ``self.``-bound and resolved at runtime via MRO.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua.loops.context_rendering import render_llm_content, should_include_chat_record
from tinycua.loops.node import build_messages_with_dedupe
from tinycua.models.node_input import convert_node_input_to_messages
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.types import LLMResult
    from tinycua.loops.node import Node
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)

class PromptProtocolMixin:
    """Mixin extracted from TinyCUALoop for modularity."""

    # Deterministic controller messages that are internal bookkeeping,
    # not useful context for downstream LLM nodes.
    _SKIP_SESSION_CONTEXT_PREFIXES = ("Scheduled analysis effort", "Analysis effort complete")

    def _inject_active_task_input(self, node: Node) -> None:
        """No-op: TaskExecutor renders markdown context in build_continuation."""
        return

    def _latest_user_text(self) -> str:
        """Return the latest external user input text."""
        for message in reversed(self.root_session.input_context):
            if isinstance(message, dict) and message.get("role") == "user":
                return str(message.get("content", ""))
            content = getattr(message, "content", None)
            if content is not None:
                return str(content)
        return ""

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
        node_input = None
        if self.queue.current is node:
            node_input = self.queue.input_for_current()
        context_session = node.session or self.root_session
        if (
            node.node_id == "query_analyst"
            and node_input in (None, {})
            and self.root_session.input_context
        ):
            node_input = list(self.root_session.input_context)
        original_instruction = None
        if override_instructions is not None:
            original_instruction = node._instruction  # noqa: SLF001 - transport shim.
            node._instruction = override_instructions  # noqa: SLF001 - transport shim.
        try:
            return node.build_messages(
                context_session,
                node_input or {},
                self._resolved_tools_for_prompt,
            )
        finally:
            if original_instruction is not None:
                node._instruction = original_instruction  # noqa: SLF001

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
        # Filter out deterministic controller noise before any path
        filtered_context = [
            entry for entry in context_session.session_context
            if not (
                isinstance(
                    entry.get("content", "") if isinstance(entry, dict) else entry.content,
                    str,
                )
                and (
                    entry.get("content", "") if isinstance(entry, dict) else entry.content
                ).startswith(self._SKIP_SESSION_CONTEXT_PREFIXES)
            )
        ]
        if not filtered_context:
            return
        if policy.dedupe_by_origin_record_id:
            messages.extend(
                build_messages_with_dedupe(
                    Session(session_context=filtered_context),
                    dedupe_by_origin_record_id=True,
                    skip_record_ids=skip_record_ids,
                )
            )
            return
        for entry in filtered_context:
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
            role = message["role"]
            if role == "user" and node.node_id != "query_analyst":
                role = "assistant"
            self._append_nonblank_message(
                messages,
                role,
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

    def _forced_tool_choice_for_node(
        self,
        agent: Agent,
        node: Node,
        resolved_tools: list[Tool],
    ) -> str | dict[str, Any] | None:
        """Return provider-compatible forced tool_choice for tool-required nodes.

        Always uses ``"required"`` because the tool list is already narrowed to
        the single required tool by :meth:`_llm_tools_for_required_choice`.
        The object form ``{"type": "function", "function": {"name": ...}}`` is
        OpenAI-hosted-API-only and crashes local servers (LM Studio, Ollama,
        vLLM, etc.) with HTTP 400.  Since ``"required"`` + a single tool list
        entry is functionally identical, we use it universally.
        """
        required = self._required_single_tool_choice_name(node)
        if required is None and [tool.name for tool in resolved_tools] == ["terminate"]:
            required = "terminate"
        if required is None:
            if node.node_id == "task_analyzer":
                return "required"
            return None
        if required not in {tool.name for tool in resolved_tools}:
            return None
        return "required"

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
        }.get(node.node_id)

    def _missing_or_required_tool_name(self, node: Node, error_text: str) -> str | None:
        """Return the most likely missing required tool for a retry message."""
        for tool_name in getattr(node.config.retry_policy, "required_tool_calls", []):
            if tool_name and tool_name in error_text:
                return str(tool_name)
        for tool_name in (
            "task_result_update",
            "task_review_decision",
            "task_update",
            "task_decompose",
            "task_init",
            "terminate",
            "select_query_route",
            "select_worker_route",
        ):
            if tool_name in error_text:
                return tool_name
        return self._required_single_tool_choice_name(node)
