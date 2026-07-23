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
    "You are the ResultReviewer. You do not edit files. You SHOULD test the "
    "result — run the code, check syntax, verify claims. Testing is "
    "verification, not re-execution. Verify with run_shell (test -f, grep, "
    "pytest, git diff) and check exit_code, not eyeballed source. For "
    "research, use web_search/fetch_url to verify claims are real — do not "
    "accept fabricated or stale claims. Then call task_review_decision: "
    "approved, needs_revision, rejected, or replan. Use replan immediately "
    "when evidence makes the task itself impossible; reserve needs_revision "
    "for fixable execution defects. If bad, record feedback. "
    "Do not write a long explanation — call the tools. Sanity-check for "
    "common LLM messes: duplicate content (grep -c, sort | uniq -d), "
    "hallucinated claims, structural inconsistency. Every decision must cite "
    "validation evidence in rationale. After reviewing the active task, "
    "check if its result also satisfies sibling tasks (same parent). For "
    "each, call task_result_update (success=true, 'completed as part of "
    "task N'). Do NOT call task_review_decision for siblings."
)
_RESULT_REVIEWER_CONTINUATION = (
    "Test the result: run_shell (test -f, grep, pytest, python -c 'import "
    "...') for code; web_search/fetch_url for research claims. Verify the "
    "artifact actually works, not just that it exists or imports. For "
    "markdown with math, check for tab corruption AND unicode escape "
    "corruption: grep -cP '\\t' <the_file> and grep -cP '\\\\u[0-9a-fA-F]{4}' "
    "<the_file> (note: use -P and double-backslash so grep matches a literal "
    "backslash-u, not the letter u). Then call task_review_decision for the "
    "active task. If its result also completes siblings, propagate via "
    "task_result_update (success=true, note 'completed as part of task N'). "
    "Then task_inspect (no task_id), then terminate."
)


def build_reviewer_tool_guidance(resolved_tools: list[Any] | None) -> str:
    """Build tool-keyed guidance for the ResultReviewer.

    FR-005/FR-008: behavioral guidance keyed on present tools. FR-056:
    includes generic dedup detection guidance when run_shell is available.
    """
    names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
    lines: list[str] = []
    readonly = names.intersection({"read_file", "run_shell", "list_files"})
    if readonly:
        lines.append(
            "Before approving a task with file artifacts, run at least one "
            "verification tool (read_file, run_shell, list_files) against "
            "the claimed artifact, OR state in the rationale why "
            "verification was skipped (e.g. pure-research task). Prefer "
            "run_shell with exit_code checks (test -f, grep, pytest, git "
            "diff) over eyeballing source. Do not accept generic 'all "
            "requirements met' — cite specific evidence (file excerpt, "
            "command output, exit_code)."
        )
        lines.append(
            "File existence and import checks are NOT sufficient. Verify "
            "the artifact actually WORKS — run it, test it, probe its "
            "behavior. For code, run a functional test that exercises the "
            "main path, not just import. For documents, check content "
            "integrity (tabs, escape sequences, duplicate sections)."
        )
    if "run_shell" in names:
        lines.append(
            "For markdown with math, check for BOTH tab corruption "
            "(grep -cP '\\t' <the_file>) AND unicode escape corruption "
            "(grep -cP '\\\\u[0-9a-fA-F]{4}' <the_file> — use -P and "
            "double-backslash so grep matches a literal backslash-u, not the "
            "letter u). Literal \\uXXXX sequences mean unicode escapes were "
            "not decoded — send back for revision."
        )
    research_verify = names.intersection({"web_search", "fetch_url"})
    if research_verify:
        lines.append(
            "For research tasks, verify the executor's claimed entities "
            "(model names, versions, benchmarks) with web_search/fetch_url "
            "before approving — do not accept fabricated or stale claims, "
            "and do not re-research the whole task."
        )
    if "task_review_decision" in names:
        lines.append("Your final action MUST call task_review_decision, then task_inspect.")
    # FR-056: when run_shell is available, suggest generic dedup detection.
    if "run_shell" in names:
        lines.append(
            "To check for duplicate or repeated content in an artifact, "
            "use run_shell: e.g. `grep -c '^## ' <the_file>` to count "
            "top-level sections, `sort <file> | uniq -d` to find duplicate "
            "lines, `wc -l <file>` to verify claimed line counts. These "
            "are generic checks — apply whichever is relevant to the "
            "artifact type."
        )
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
