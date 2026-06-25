"""Markdown-synthesis retry templates + registry + parser (FR-087..FR-093).

When a node's LLM response completes without emitting its required state tool,
lazy retry makes one no-tools non-streaming LLM continuation asking the model
to fill a small markdown template. This module owns the v1 templates, the
node→tool registry, and the parser that extracts fields from the response.

v1 covers: result_reviewer, task_executor, query_analyst, worker.
Out of scope (v1): task_create, task_assessor, task_analyzer (stay 100%
standard). ``terminate``-only missing keeps ``_direct_terminate`` (no template).
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# v1 markdown templates
# ---------------------------------------------------------------------------

RESULT_REVIEWER_TEMPLATE = """\
# Review Assessment : [approved | rejected | needs_revision | replan]
# Review Summary
<your summary here>
# Task ID
<task id>
"""

TASK_EXECUTOR_TEMPLATE = """\
# Status : [completed | failed | replan]
# Summary
<your summary here>
# Task ID
<task id>
"""

ROUTE_TEMPLATE = """\
# Route : {labels}
# Rationale
<one line>
"""

# Registry: node_id → (target_tool_name, template_str).
# The template's {labels} placeholder is filled at call time for route nodes.
LAZY_TEMPLATES: dict[str, tuple[str, str]] = {
    "result_reviewer": ("task_review_decision", RESULT_REVIEWER_TEMPLATE),
    "task_executor": ("task_result_update", TASK_EXECUTOR_TEMPLATE),
    "query_analyst": ("select_query_route", ROUTE_TEMPLATE),
    "worker": ("select_worker_route", ROUTE_TEMPLATE),
}

# Registered state tools that lazy retry may synthesize.
LAZY_STATE_TOOLS: frozenset[str] = frozenset({
    "task_result_update",
    "task_review_decision",
    "select_query_route",
    "select_worker_route",
})

# Allowed enum values per template field.
_REVIEWER_DECISIONS = {"approved", "rejected", "needs_revision", "replan"}
_EXECUTOR_STATUSES = {"completed", "failed", "replan"}

# ponytail: regex parser; upgrade to a real markdown parser if templates grow
# complex or nested. Two section shapes:
#   inline:  "# Header : value"
#   block:   "# Header\n<text until next header or end>"
_INLINE_RE = re.compile(r"^#\s*(.+?)\s*:\s*(.+?)\s*$", re.MULTILINE)
_BLOCK_HEADER_RE = re.compile(r"^#\s*(.+?)\s*$", re.MULTILINE)


def parse_lazy_markdown(
    node_id: str,
    markdown: str,
    *,
    allowed_labels: set[str] | None = None,
) -> dict[str, Any] | None:
    """Parse a lazy-retry markdown response into tool-call fields.

    Args:
        node_id: The node whose template was filled.
        markdown: The LLM's markdown synthesis response.
        allowed_labels: Optional route-label allowlist for route nodes.

    Returns:
        Dict of parsed fields keyed by the target tool's parameter names, or
        None on parse failure / missing required field / invalid enum.
    """
    if node_id not in LAZY_TEMPLATES:
        return None
    text = (markdown or "").strip()
    if not text:
        return None
    sections = _extract_sections(text)
    if not sections:
        return None
    if node_id == "result_reviewer":
        return _parse_reviewer(sections)
    if node_id == "task_executor":
        return _parse_executor(sections)
    return _parse_route(sections, allowed_labels)


def _extract_sections(text: str) -> dict[str, str]:
    """Split markdown into {header: value_or_body} preserving insertion order."""
    sections: dict[str, str] = {}
    # Find all header positions (both inline and block forms).
    headers = list(_BLOCK_HEADER_RE.finditer(text))
    # Headers with a ": value" inline form are captured separately below.
    for match in _INLINE_RE.finditer(text):
        header = match.group(1).strip().lower()
        value = match.group(2).strip()
        sections[header] = value
    # Block-form headers (no inline ": value") capture the body until the next
    # header. Skip headers that already appeared as inline (they take
    # precedence and were set above).
    inline_headers = {m.group(1).strip().lower() for m in _INLINE_RE.finditer(text)}
    for i, match in enumerate(headers):
        header = match.group(1).strip().lower()
        if header in inline_headers:
            continue
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        sections[header] = body
    return sections


def _parse_reviewer(sections: dict[str, str]) -> dict[str, Any] | None:
    """Parse result_reviewer template → {decision, rationale, task_id}."""
    decision = sections.get("review assessment")
    rationale = sections.get("review summary")
    task_id = sections.get("task id")
    if not decision or not rationale or not task_id:
        return None
    decision = decision.strip().lower()
    if decision not in _REVIEWER_DECISIONS:
        return None
    return {
        "decision": decision,
        "rationale": rationale.strip(),
        "task_id": task_id.strip(),
    }


def _parse_executor(sections: dict[str, str]) -> dict[str, Any] | None:
    """Parse task_executor template → {content, success, task_id}."""
    status = sections.get("status")
    content = sections.get("summary")
    task_id = sections.get("task id")
    if not status or not content or not task_id:
        return None
    status = status.strip().lower()
    # v1: completed → success=true, failed → success=false.
    # 'replan' is a reviewer concept, not an executor outcome — reject.
    if status == "completed":
        success = True
    elif status == "failed":
        success = False
    else:
        return None
    return {
        "content": content.strip(),
        "success": success,
        "task_id": task_id.strip(),
    }


def _parse_route(sections: dict[str, str], allowed_labels: set[str] | None) -> dict[str, Any] | None:
    """Parse query_analyst/worker route template → {route}."""
    route = sections.get("route")
    rationale = sections.get("rationale")
    if not route or not rationale:
        return None
    route = route.strip()
    if allowed_labels is not None and route not in allowed_labels:
        return None
    return {"route": route}
