"""Draft-tool exposure and safe tool-result feedback helpers."""

from __future__ import annotations

from copy import copy
import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import ToolExecutor
from tinycua.agent.tools.native.output_persist import (
    SessionToolResultStore,
    persist_if_oversized,
)
from tinycua.loops.node_contract import LifecyclePhase, phase_tool_names

if TYPE_CHECKING:
    from tinycua_sdk.tools.decorators import Tool

    from tinycua.loops.node import Node


DRAFTABLE_TOOL_NAMES = {
    "task_init",
    "task_create",
    "task_update",
    "task_decompose",
    "task_shrink",
    "task_assessment_decision",
    "task_review_plan",
    "task_review_decision",
    "digest_information",
    "node_handoff",
}
_MANAGED_DRAFT_EDITORS = {
    "json_draft_write": (
        "write_file",
        "Write content to the current managed JSON draft. This cannot write workspace files.",
        {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Full draft content."}
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    ),
    "json_draft_replace": (
        "str_replace",
        "Replace text in the current managed JSON draft. This cannot edit workspace files.",
        {
            "type": "object",
            "properties": {
                "old_string": {"type": "string", "description": "Text to replace."},
                "new_string": {"type": "string", "description": "Replacement text."},
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace every occurrence when true.",
                },
            },
            "required": ["old_string", "new_string"],
            "additionalProperties": False,
        },
    ),
}
logger = logging.getLogger(__name__)


class JsonDraftMixin:
    """Provide session-bound drafts without bloating the main loop."""

    def _reset_tool_result_store(self) -> None:
        """Start an isolated temporary result store for the root session."""
        store = getattr(self, "_tool_result_store", None)
        if store is not None:
            store.cleanup()
        self._tool_result_store = SessionToolResultStore(self.root_session.session_id)

    def _bind_tool_result_tools(self, tools: list[Tool], node: Node) -> None:
        """Authorize this node to retrieve only its own persisted results."""
        for tool in tools:
            binder = getattr(tool, "bind_tool_result_access", None)
            if callable(binder):
                binder(
                    self._tool_result_store, self.root_session.session_id, node.node_id
                )
            web_cache_binder = getattr(tool, "bind_web_cache", None)
            if callable(web_cache_binder):
                web_cache_binder(self._tool_result_store)

    def _persist_tool_result(
        self, content: str, call_id: str, tool_name: str, node: Node | None
    ) -> str:
        """Persist oversized output for its producing node when available."""
        return persist_if_oversized(
            content,
            call_id,
            tool_name=tool_name,
            store=self._tool_result_store,
            owner_node_id=node.node_id if node is not None else "",
        )

    def _bind_draft_file_tools(self, tools: list[Tool], node: Node) -> None:
        """Limit native file access to this execution's managed draft directory."""
        draft_dir = None
        if (
            node.node_id != "task_executor"
            and {tool.name for tool in tools} & DRAFTABLE_TOOL_NAMES
            and self.workspace_dir is not None
        ):
            draft_dir = (
                self.workspace_dir
                / ".tinycua"
                / self.root_session.session_id
                / "tmp"
                / self._draft_execution_id
            )
        for tool in tools:
            binder = getattr(tool, "bind_managed_draft_dir", None)
            if callable(binder):
                binder(draft_dir)

    @staticmethod
    def _managed_draft_editors(tools: list[Tool]) -> list[Tool]:
        """Return path-free, per-call aliases for managed draft editing."""
        available = {tool.name: tool for tool in tools}
        editors: list[Tool] = []
        for alias, (
            canonical_name,
            description,
            parameters,
        ) in _MANAGED_DRAFT_EDITORS.items():
            canonical = available.get(canonical_name)
            if canonical is None:
                continue
            editor = copy(canonical)
            editor.name = alias
            editor.description = description
            editor.parameters = parameters
            setattr(editor, "_tinycua_canonical_tool", canonical)
            editors.append(editor)
        return editors

    @staticmethod
    def _canonical_tool(tool: Tool) -> Tool:
        """Return a managed-draft alias's canonical execution tool."""
        return getattr(tool, "_tinycua_canonical_tool", tool)

    @staticmethod
    def _phase_draft_creator(tools: list[Tool], targets: set[str]) -> list[Tool]:
        """Return a draft creator limited to this lifecycle phase's targets."""
        creator = next(
            (tool for tool in tools if tool.name == "json_draft_create"), None
        )
        if creator is None:
            return []
        creator = copy(creator)
        creator.parameters = {
            "type": "object",
            "properties": {"target_tool": {"type": "string", "enum": sorted(targets)}},
            "required": ["target_tool"],
            "additionalProperties": False,
        }
        creator._allowed_targets = set(targets)
        return [creator]

    def _inject_draft_path(
        self, node: Node | None, tool: Tool, arguments: dict[str, Any]
    ) -> str | None:
        """Inject a managed draft path for a canonical editor."""
        return self._inject_managed_draft_path(
            node,
            tool.name,
            arguments,
            native_write=hasattr(tool, "bind_file_execution"),
        )

    def _reviewer_draft_phase_tools(
        self,
        node: Node,
        phase: Any,
        phase_targets: set[str],
        tools: list[Tool],
        phase_tools: list[Tool],
    ) -> list[Tool]:
        """Restrict reviewer mutation to a created managed draft."""
        if node.node_id != "result_reviewer":
            return phase_tools
        phase_tools = [
            tool
            for tool in phase_tools
            if tool.name not in {"write_file", "str_replace"}
        ]
        if (
            getattr(phase, "value", phase) not in {"plan", "commit"}
            or not phase_targets
        ):
            return phase_tools
        if self._managed_draft_path(node):
            phase_tools = [
                tool for tool in phase_tools if tool.name != "json_draft_create"
            ]
            return [*phase_tools, *self._managed_draft_editors(tools)]
        phase_tools = [
            tool
            for tool in phase_tools
            if tool.name not in {"json_draft_commit", "json_draft_create"}
        ]
        return [*phase_tools, *self._phase_draft_creator(tools, phase_targets)]

    def _phase_tool_names(
        self, node: Node, tools: list[Tool], phase: LifecyclePhase
    ) -> tuple[LifecyclePhase, set[str]]:
        """Resolve the phase and its canonical tool names."""
        if phase == LifecyclePhase.TERMINATE and not self._can_terminate(node):
            phase = LifecyclePhase.COMMIT
        return phase, phase_tool_names(
            node.node_id,
            {tool.name for tool in tools if not tool.name.startswith("json_draft_")},
            phase,
        )

    def _managed_draft_path(self, node: Node | None) -> str | None:
        """Return the sole active draft path for this node execution."""
        if node is None or node.node_id == "task_executor":
            return None
        paths = [
            draft["path"]
            for draft in self.root_session.json_drafts.values()
            if (
                draft["session_id"] == self.root_session.session_id
                and draft["node_id"] == node.node_id
                and draft["execution_id"] == self._draft_execution_id
            )
        ]
        return paths[0] if len(paths) == 1 else None

    def _inject_managed_draft_path(
        self,
        node: Node | None,
        name: str,
        arguments: dict[str, Any],
        *,
        native_write: bool = False,
    ) -> str | None:
        """Route draft edits to their runtime-selected path."""
        if name not in {"read_file", "write_file", "str_replace"}:
            return None
        if path := self._managed_draft_path(node):
            arguments["path"] = path
            if native_write and name == "write_file":
                arguments["replace"] = True
            return None
        if (
            node is not None
            and node.node_id != "task_executor"
            and name in {"write_file", "str_replace"}
            and {tool.name for tool in node.config.tool_policy.node_tools}
            & DRAFTABLE_TOOL_NAMES
        ):
            return "managed_draft_required"
        return None

    def _with_json_draft_tools(self, node: Node, tools: list[Tool]) -> list[Tool]:
        """Expose bounded draft editing beside stateful structured commits."""
        del node
        if not {tool.name for tool in tools} & DRAFTABLE_TOOL_NAMES:
            return tools
        from tinycua.tools.json_drafts import JsonDraftCommitTool, JsonDraftCreateTool

        return [
            *tools,
            JsonDraftCreateTool(),
            JsonDraftCommitTool(),
        ]

    @staticmethod
    def _redacted_tool_history(result: dict[str, Any]) -> dict[str, Any]:
        """Remove attachment payloads before keeping a durable chat record."""
        output = result.get("output")
        if not isinstance(output, dict) or "attachments" not in output:
            return result
        redacted = dict(result)
        safe_output = dict(output)
        safe_output["attachments"] = [
            {
                "filename": getattr(attachment, "filename", None),
                "mime_type": getattr(attachment, "mime_type", None),
            }
            for attachment in output["attachments"]
        ]
        redacted["output"] = safe_output
        return redacted

    def _tool_result_feedback_messages(
        self,
        tool_results: list[dict[str, Any]],
        normalized_tool_calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build provider-valid feedback for one assistant tool-call batch."""
        call_ids = {
            str(tool_call["id"]): tool_call
            for tool_call in normalized_tool_calls
            if tool_call.get("id")
        }
        messages: list[dict[str, Any]] = []
        for tool_result in tool_results:
            tool_call_id = str(tool_result.get("call_id") or "")
            if tool_call_id not in call_ids:
                continue
            tool_name = tool_result.get("name", "")
            output = tool_result.get("output")
            if isinstance(output, dict) and "attachments" in output:
                messages.append(
                    {
                        "role": "tool_result",
                        "call_id": tool_call_id,
                        "content": output.get("content", "Image attached."),
                        "attachments": output["attachments"],
                    }
                )
                continue
            content = tool_result.get("prompt_content")
            if not isinstance(content, str):
                content = persist_if_oversized(
                    json.dumps(tool_result, default=str),
                    tool_call_id,
                    tool_name=tool_name,
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": content,
                }
            )
        return messages

    async def _prepare_json_draft_commit(
        self, agent: Any, arguments: dict[str, Any], allowed_tools: dict[str, Tool]
    ) -> tuple[str, dict[str, Any], tuple[Tool, str]]:
        """Expand a valid draft commit into its canonical target invocation."""
        draft_tool = allowed_tools["json_draft_commit"]
        try:
            output = await ToolExecutor.execute(draft_tool, arguments, agent)
        except Exception as exc:  # noqa: BLE001 - return bounded tool feedback.
            raise ValueError(str(exc)) from exc
        if not isinstance(output, dict) or not output.get("success"):
            raise ValueError(str(output.get("error", "invalid_draft")))
        target = output.get("target_tool")
        target_arguments = output.get("arguments")
        draft_id = output.get("draft_id")
        if (
            not isinstance(target, str)
            or not isinstance(target_arguments, dict)
            or target not in allowed_tools
            or not isinstance(draft_id, str)
        ):
            raise ValueError("draft_target_not_available")
        return target, target_arguments, (draft_tool, draft_id)

    @staticmethod
    def _log_tool_call_args(name: str, arguments: dict[str, Any]) -> None:
        """Log bounded tool-call diagnostics without leaking draft contents."""
        if name.startswith("json_draft_"):
            logger.debug("tool=%s draft arguments redacted", name)
            return
        try:
            preview = json.dumps(arguments, default=str)[:200]
        except (TypeError, ValueError):
            preview = str(arguments)[:200]
        logger.debug("tool=%s args=%s", name, preview)
