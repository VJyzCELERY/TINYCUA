"""Role-specific projections of the lossless task review journal."""

from __future__ import annotations

from typing import Any


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
