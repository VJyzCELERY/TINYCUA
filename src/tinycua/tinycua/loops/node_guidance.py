"""Generic node guidance: prompt constants and tool-keyed guidance builders.

Extracted from ``task_nodes.py`` so node-specific prompt enhancements evolve
independently of the node plumbing. Currently holds the ResultReviewer
guidance; other nodes' guidance can move here in the future.

FR-059: the reviewer instruction enforces validation evidence in every
``task_review_decision`` rationale — a validator in ``validation_retry_mixin``
backs it up at runtime. The validation logic lives here (not in the mixin) to
keep the mixin under the LOC gate and centralize reviewer rules.

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
    "You are the ResultReviewer. You do not edit files. Verify the result "
    "against the active task's requirements and acceptance criteria using "
    "checks appropriate to the claimed outcome and available tools. Testing is "
    "verification, not re-execution. Exercise material behavior, inspect outputs, "
    "and verify consequential claims with concrete evidence. Do not accept "
    "fabricated or unsupported claims. Determine approved, needs_revision, "
    "rejected, or replan. Use replan immediately "
    "when evidence makes the task itself impossible; reserve needs_revision "
    "for fixable execution defects. If bad, record feedback. "
    "Do not write a long explanation — call the tools. When relevant, check for "
    "duplicate content, hallucinated claims, and structural inconsistency. "
    "Every decision must cite "
    "validation evidence in rationale. Review and decide only the active task."
)
_RESULT_REVIEWER_CONTINUATION = (
    "Verify the result against the active task's acceptance criteria. Choose "
    "checks appropriate to the artifact or claim, exercise required behavior "
    "where possible, and cite concrete evidence. Then summarize the active-task "
    "review conclusion."
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
            "Before approving, use available verification tools to gather "
            "evidence tied to the acceptance criteria, or state why direct "
            "verification is unavailable. Do not accept generic 'all requirements "
            "met' claims; cite the specific evidence observed."
        )
        lines.append(
            "When the task requires behavior, verify that it actually works "
            "rather than checking existence alone. Choose the smallest relevant "
            "check for the claimed outcome and available environment."
        )
    research_verify = names.intersection({"web_search", "fetch_url"})
    if research_verify:
        lines.append(
            "Verify material external claims with appropriate authoritative "
            "sources before approving, without re-researching the whole task."
        )
    if "task_review_decision" in names:
        lines.append("Commit the review with task_review_decision.")
    if "terminate" in names:
        lines.append("Call terminate now.")
    if not lines:
        return ""
    return "Tool guidance: " + " ".join(lines)


def validate_reviewer_rationale(tool_calls: list[dict[str, Any]]) -> list[str]:
    """Check that task_review_decision rationale has validation evidence (FR-059).

    Returns a list of error strings (empty if valid). The rationale MUST
    include validation evidence so the executor can verify findings
    deterministically:
    - approved: ``[validated]: <command+result confirming the outcome>``
    - needs_revision/rejected/replan: ``[finding]: <issue> [validate]:
      <runnable command the executor can use to verify the fix>``

    Generic across artifact types — code (pytest, grep), research
    (web_search URL), data (wc, run_python).
    """
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
        decision = arguments.get("decision", "")
        rationale = (arguments.get("rationale") or "").strip()
        if not rationale:
            return [
                "task_review_decision rationale is required — include "
                "validation evidence. For approved: '[validated]: "
                "<command+result>'. For needs_revision/rejected/replan: "
                "'[finding]: <issue> [validate]: <command>'."
            ]
        lowered = rationale.lower()
        if decision == "approved" and "[validated]" not in lowered:
            return [
                "Approved decisions must include '[validated]: "
                "<command+result>' in the rationale — cite the "
                "evidence that confirms the outcome."
            ]
        if decision in ("needs_revision", "rejected", "replan") and "[validate]" not in lowered:
            return [
                "Non-approved decisions must include '[validate]: "
                "<command>' in the rationale — provide a runnable "
                "command the executor can use to verify the fix."
            ]
        return []
    return []
