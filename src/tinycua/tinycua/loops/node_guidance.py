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
    "You are the ResultReviewer. Do not edit files. Review only the active task outcome. "
    "Original requests and hard constraints outrank generated text. Root acceptance "
    "criteria are leaf context and root gates. Match each material claim and criterion to "
    "evidence. Runtime-check behavior, inspect artifacts, and authoritatively source "
    "external claims; reuse proven evidence and skip unrelated suites. Reject duplicate, "
    "hallucinated, or inconsistent claims. Use needs_revision for defects; replan a wrong "
    "task, approach, or substantial sibling work. Incidental sibling effects are not "
    "completion. Postpone blocked work; compromise only after failure. Record "
    "comprehensive review_summary, rationale report, and active-task findings in the "
    "decision tool. Do not write a long explanation outside it. Approval requires no OPEN "
    "findings. Pass cross-task facts only through "
    "explicit context_updates; do not approve unfinished tasks or trust executor claims "
    "alone."
)
_RESULT_REVIEWER_CONTINUATION = (
    "Judge only the active task description and result. Root acceptance criteria are "
    "advisory for a leaf and mandatory when reviewing the root. Summarize the "
    "evidence-backed active-task conclusion."
)


def build_reviewer_tool_guidance(resolved_tools: list[Any] | None) -> str:
    """Build tool-keyed guidance for the ResultReviewer.

    FR-005/FR-008: acceptance-driven guidance keyed on present tools.
    """
    names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
    lines: list[str] = []
    if "task_review_plan" in names:
        lines.append(
            "Before seeing Executor conclusions, commit one falsification check for "
            "every root acceptance criterion. Classify only inherently subjective "
            "criteria as judgment."
        )
    readonly = names.intersection({"read_file", "run_shell", "list_files"})
    if readonly:
        lines.append(
            "Match evidence to acceptance criteria: use focused runtime checks to "
            "show behavior actually works for behavioral claims, and inspection "
            "for artifact claims. Run explicitly requested "
            "verification unless exact current evidence already proves it. Prefer "
            "the narrow relevant check, not unrelated suites."
        )
    research_verify = names.intersection({"web_search", "fetch_url"})
    if research_verify:
        lines.append(
            "Use authoritative sources when they help assess material external claims."
        )
    if "task_review_decision" in names:
        lines.append(
            "Commit the review with task_review_decision, including review_summary, "
            "new_findings, finding_updates, and root criterion assessments. Cite only "
            "actual current-review observations for empirical support. Use "
            "context_updates only for explicit cross-task facts."
        )
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


def failed_tool_retry_message(llm_result: Any) -> str:
    """Return exact corrective guidance for the latest rejected tool call."""
    succeeded: set[str] = set()
    for item in reversed(llm_result.metadata.get("tool_results", [])):
        if not isinstance(item, dict):
            continue
        outcome = item.get("outcome")
        output = item.get("output")
        name = (
            outcome.get("tool_name") if isinstance(outcome, dict) else None
        ) or item.get("name")
        success = (
            outcome.get("success")
            if isinstance(outcome, dict)
            else output.get("success")
            if isinstance(output, dict)
            else None
        )
        if success is True and isinstance(name, str):
            succeeded.add(name)
            continue
        sources = (outcome, output, item)
        error = next(
            (
                source.get("error")
                for source in sources
                if isinstance(source, dict) and source.get("error")
            ),
            None,
        )
        if (
            isinstance(error, str)
            and error.strip()
            and isinstance(name, str)
            and name not in succeeded
        ):
            return f"{name} failed: {error.strip()} Correct it and call {name} again."
    return ""
