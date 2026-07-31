"""Draft-tool exposure and safe tool-result feedback helpers."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import ToolExecutor
from tinycua.agent.tools.native.output_persist import persist_if_oversized

if TYPE_CHECKING:
    from tinycua_sdk.tools.decorators import Tool

    from tinycua.loops.node import Node


DRAFTABLE_TOOL_NAMES = {
    "task_init",
    "task_create",
    "task_update",
    "task_decompose",
    "task_shrink",
    "task_result_update",
    "task_assessment_decision",
    "task_review_plan",
    "task_review_decision",
    "digest_information",
    "node_handoff",
    "todo_write",
}
logger = logging.getLogger(__name__)


class JsonDraftMixin:
    """Provide session-bound drafts without bloating the main loop."""

    def _with_json_draft_tools(self, node: Node, tools: list[Tool]) -> list[Tool]:
        """Expose bounded draft editing beside stateful structured commits."""
        del node
        if not {tool.name for tool in tools} & DRAFTABLE_TOOL_NAMES:
            return tools
        from tinycua.tools.json_drafts import (
            JsonDraftCommitTool,
            JsonDraftCreateTool,
            JsonDraftReadTool,
            JsonDraftReplaceTool,
        )

        return [
            *tools,
            JsonDraftCreateTool(),
            JsonDraftReadTool(),
            JsonDraftReplaceTool(),
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
    ) -> tuple[str, dict[str, Any], tuple[Tool, str, int]]:
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
        revision = arguments.get("expected_revision")
        if (
            not isinstance(target, str)
            or not isinstance(target_arguments, dict)
            or target not in allowed_tools
            or not isinstance(draft_id, str)
            or not isinstance(revision, int)
        ):
            raise ValueError("draft_target_not_available")
        return target, target_arguments, (draft_tool, draft_id, revision)

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
