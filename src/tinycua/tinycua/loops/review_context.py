"""Role-specific projections of the lossless task review journal."""

from __future__ import annotations

from hashlib import sha256
from typing import Any


_MAX_EVIDENCE_LINE_CHARS = 3500


def _bounded_evidence_line(line: str) -> str:
    """Bound one prompt line while retaining exact provenance in task state."""
    if len(line) <= _MAX_EVIDENCE_LINE_CHARS:
        return line
    suffix = (
        "…[prompt preview truncated; "
        f"total_chars={len(line)}; sha256={sha256(line.encode()).hexdigest()}]"
    )
    return f"{line[: _MAX_EVIDENCE_LINE_CHARS - len(suffix)]}{suffix}"


def render_executor_review_context(task: Any) -> list[str]:
    """Return all current open findings and their complete latest rationale."""
    findings = [
        finding for finding in task.review_findings if finding.get("status") == "OPEN"
    ]
    if not findings:
        return []
    lines = ["", "## Current Review Findings"]
    lines.extend(
        f"- {finding['finding_id']} [OPEN]: {finding['summary']}"
        for finding in findings
    )
    events = {
        event.get("event_id"): event
        for event in task.reviewer_decisions
        if event.get("event_id")
    }
    rendered: set[str] = set()
    for finding in findings:
        event_id = finding.get("updated_event_id") or finding.get("created_event_id")
        if not isinstance(event_id, str) or event_id in rendered:
            continue
        event = events.get(event_id)
        if event is None:
            continue
        detail = str(
            event.get("rationale") or event.get("review_summary") or ""
        ).strip()
        if detail:
            lines.extend([f"Complete rationale from {event_id}:", detail])
        rendered.add(event_id)
    return lines


def render_reviewer_finding_ledger(task: Any) -> list[str]:
    """Return a compact active-task ledger for cross-checking finding identity."""
    if not task.review_findings:
        return []
    lines = ["", "## Finding Ledger"]
    lines.extend(
        f"- {finding['finding_id']} [{finding['status']}] "
        f"(event {finding.get('updated_event_id', '?')}): {finding['summary']}"
        for finding in task.review_findings
    )
    lines.append(
        "Reuse or reopen an existing finding for the same defect; do not create a duplicate."
    )
    return lines


def render_executor_tool_evidence(task: Any) -> list[str]:
    """Return bounded runtime provenance for claims in the Executor report."""
    if task.result is None:
        return []
    evidence = task.result.metadata.get("tool_results", [])
    if not isinstance(evidence, list):
        return []
    lines = [
        "## Executor tool-call evidence",
        "Supporting context from Executor tool calls; output previews may be "
        "truncated. These are not independent Reviewer observations.",
    ]
    for item in evidence[-16:]:
        if not isinstance(item, dict):
            continue
        outcome = item.get("outcome")
        if not isinstance(outcome, dict):
            continue
        name = str(outcome.get("tool_name") or item.get("name") or "tool")
        bits = [
            f"call_id={outcome.get('call_id') or '?'}",
            f"success={outcome.get('success')}",
        ]
        if outcome.get("exit_code") is not None:
            bits.append(f"exit_code={outcome['exit_code']}")
        if outcome.get("error"):
            bits.append(f"error={outcome['error']}")
        invocation = outcome.get("invocation")
        if isinstance(invocation, dict):
            bits.extend(f"{key}={value}" for key, value in invocation.items())
        if outcome.get("truncated"):
            bits.append("output_preview_truncated=True")
        if item.get("artifact_path"):
            bits.append(f"audit={item['artifact_path']}")
        lines.append(_bounded_evidence_line(f"- {name}: " + "; ".join(bits)))
    if len(lines) == 2:
        return []
    omitted = max(0, len(evidence) - 16)
    if omitted:
        lines.append(f"- ({omitted} earlier tool results omitted)")
    return lines
