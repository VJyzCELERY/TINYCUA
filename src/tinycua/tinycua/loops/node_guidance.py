"""Generic node guidance: prompt constants and tool-keyed guidance builders.

Extracted from ``task_nodes.py`` so node-specific prompt enhancements evolve
independently of the node plumbing. Currently holds the ResultReviewer
guidance; other nodes' guidance can move here in the future.

FR-060: ``summarize_tool_result`` lives here so the recovery loop can
import it without depending on the CLI layer. The CLI re-exports it.
"""

from __future__ import annotations

import json
from typing import Any


def _truncate(value: str, limit: int) -> str:
    """Truncate long strings with an ellipsis marker."""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…[truncated]"


def summarize_tool_result(content: str) -> str:
    """Summarize a tool result without dumping its JSON body.

    Moved here from ``cli/live_stream.py`` so the recovery loop can import
    it without a CLI dependency. The CLI re-exports it for backward compat.
    """
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return _truncate(content, 500)
    if not isinstance(payload, dict):
        return _truncate(content, 500)
    output = payload.get("output")
    status = ""
    if isinstance(output, dict):
        success = output.get("success")
        if success is not None:
            status = f"success={success}"
        if output.get("path"):
            return f"{status} path={output['path']}".strip()
        if output.get("task_id"):
            task_bits = [status, f"task_id={output['task_id']}"]
            if output.get("status"):
                task_bits.append(f"status={output['status']}")
            if output.get("decision"):
                task_bits.append(f"decision={output['decision']}")
            return " ".join(bit for bit in task_bits if bit)
        if output.get("exit_code") is not None:
            return f"exit_code={output.get('exit_code')} timed_out={output.get('timed_out')}"
    if isinstance(output, list):
        return f"items={len(output)}"
    if payload.get("error"):
        return f"error={payload['error']}"
    return "completed"


_RESULT_REVIEWER_INSTRUCTION = (
    "You are the ResultReviewer. You do not edit files. Review the executor's "
    "outcome against the active task and acceptance criteria context. Inspect "
    "claims with available tools when useful, then write a concise review report "
    "and determine approved, needs_revision, rejected, or replan. Use replan immediately "
    "when evidence makes the task itself impossible; reserve needs_revision "
    "for fixable execution defects. If bad, record feedback. "
    "Do not write a long explanation. When relevant, check for "
    "duplicate content, hallucinated claims, and structural inconsistency. "
    "Review and decide only the active task."
)
_RESULT_REVIEWER_CONTINUATION = (
    "Review the result against the active task and acceptance criteria context. "
    "Then summarize the active-task review conclusion."
)


def build_reviewer_tool_guidance(resolved_tools: list[Any] | None) -> str:
    """Build tool-keyed guidance for the ResultReviewer.

    FR-005/FR-008: acceptance-driven guidance keyed on present tools.
    """
    names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
    lines: list[str] = []
    readonly = names.intersection({"read_file", "run_shell", "list_files"})
    if readonly:
        lines.append(
            "Use available read-only tools when they help assess whether claimed "
            "behavior actually works against the acceptance criteria context."
        )
    research_verify = names.intersection({"web_search", "fetch_url"})
    if research_verify:
        lines.append(
            "Use authoritative sources when they help assess material external claims."
        )
    if "task_review_decision" in names:
        lines.append("Commit the review with task_review_decision.")
    if "terminate" in names:
        lines.append("Call terminate now.")
    if not lines:
        return ""
    return "Tool guidance: " + " ".join(lines)


def validate_reviewer_report(tool_calls: list[dict[str, Any]]) -> list[str]:
    """Require a free-form report with each reviewer decision."""
    for tool_call in tool_calls:
        function = tool_call.get("function") or {}
        name = function.get("name") or tool_call.get("name")
        if name != "task_review_decision":
            continue
        arguments = function.get("arguments") or tool_call.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if not str(arguments.get("rationale", "")).strip():
            return [
                "task_review_decision rationale is required as a concise review report."
            ]
    return []
