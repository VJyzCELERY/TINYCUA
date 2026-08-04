"""Validation helpers for root-review falsification state."""

from __future__ import annotations

from typing import Any

_CHECK_FIELDS = {
    "criterion_id",
    "testability",
    "falsifying_condition",
    "procedure",
    "expected_observation",
}
_ASSESSMENT_FIELDS = {
    "criterion_id",
    "result",
    "evidence_ids",
    "inference",
    "limitations",
}
_ASSESSMENT_RESULTS = {
    "supported",
    "contradicted",
    "inconclusive",
    "judgment_only",
}
_REVIEW_PREVIEW_CHARS = 240
_REVIEW_PAGE_LIMIT = 8_000


def validate_runtime_revision_anchor(runtime: Any) -> dict[str, Any] | None:
    """Validate runtime-injected result/artifact identities for one verdict.

    These identities are owned by the runtime and injected immediately before
    the atomic review commit; the model cannot provide or override them.

    Args:
        runtime: The ``runtime_result_revision`` value staged by the runtime,
            or ``None`` when the event is a legacy unanchored review.

    Returns:
        The normalized anchor dict, or ``None`` for an unanchored event.

    Raises:
        ValueError: When the anchor shape is malformed or incomplete.
    """
    if runtime is None:
        return None
    if not isinstance(runtime, dict):
        msg = "Runtime result revision anchors are invalid."
        raise ValueError(msg)
    revision_id = runtime.get("revision_id")
    content_hash = runtime.get("content_hash")
    artifact_range = runtime.get("artifact_range")
    if not isinstance(revision_id, str) or not revision_id.strip():
        msg = "Runtime result revision id is invalid."
        raise ValueError(msg)
    if not isinstance(content_hash, str) or not content_hash.strip():
        msg = "Runtime result content hash is invalid."
        raise ValueError(msg)
    if (
        not isinstance(artifact_range, dict)
        or not isinstance(artifact_range.get("from"), str)
        or not artifact_range.get("from")
        or not isinstance(artifact_range.get("to"), str)
        or not artifact_range.get("to")
    ):
        msg = "Runtime artifact range anchors are invalid."
        raise ValueError(msg)
    return {
        "revision_id": revision_id.strip(),
        "content_hash": content_hash.strip(),
        "artifact_range": {
            "from": artifact_range["from"],
            "to": artifact_range["to"],
        },
    }


def review_event_preview(event: dict[str, Any]) -> dict[str, Any]:
    """Return bounded review-event context with full-view navigation metadata."""
    summary = str(event.get("review_summary") or event.get("rationale", "")).strip()
    preview = (
        f"{summary[: _REVIEW_PREVIEW_CHARS - 3]}..."
        if len(summary) > _REVIEW_PREVIEW_CHARS
        else summary
    )
    return {
        "event_id": event["event_id"],
        "review_summary": preview,
        "review_summary_total_chars": len(summary),
        "review_summary_truncated": len(summary) > _REVIEW_PREVIEW_CHARS,
        "decision": event.get("decision", "unknown"),
    }


def review_event_page(
    event: dict[str, Any], field: str, offset: int, limit: int
) -> dict[str, Any]:
    """Return one bounded page from a review event's long-form text field."""
    if field not in {"review_summary", "rationale"}:
        raise ValueError("Review event field must be review_summary or rationale.")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("Review event offset must be a non-negative integer.")
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= _REVIEW_PAGE_LIMIT
    ):
        raise ValueError("Review event limit must be between 1 and 8000.")
    text = str(event.get(field, ""))
    end = min(offset + limit, len(text))
    return {
        "event_id": event["event_id"],
        "field": field,
        "content": text[offset:end],
        "offset": offset,
        "limit": limit,
        "total_chars": len(text),
        "next_offset": end if end < len(text) else None,
        "has_more": end < len(text),
    }


def build_review_event_metadata(
    *,
    plan: list[dict[str, str]],
    decision: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build leaf metadata or validated root assurance metadata."""
    event_metadata: dict[str, Any] = {
        "context_updates": metadata.get("context_updates", []),
    }
    if not plan:
        return event_metadata
    assessments, assurance = validate_root_assessments(
        plan, decision, metadata.get("criterion_assessments", [])
    )
    event_metadata.update(
        {
            "review_plan": plan,
            "criterion_assessments": assessments,
            "assurance_status": assurance,
        }
    )
    return event_metadata


def validate_review_plan(
    acceptance_clauses: list[dict[str, str]], checks: object
) -> list[dict[str, str]]:
    """Return a normalized plan covering every acceptance clause exactly once."""
    if not isinstance(checks, list) or not checks:
        raise ValueError("Review plan checks must be a non-empty list.")
    normalized: list[dict[str, str]] = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != _CHECK_FIELDS:
            raise ValueError("Each review check has unknown or missing fields.")
        if any(
            not isinstance(check[field], str) or not check[field].strip()
            for field in _CHECK_FIELDS
        ):
            raise ValueError("Each review check field must be a non-empty string.")
        if check["testability"] not in {"empirical", "judgment"}:
            raise ValueError("Review check testability is invalid.")
        normalized.append({field: check[field].strip() for field in _CHECK_FIELDS})

    criterion_ids = [check["criterion_id"] for check in normalized]
    if len(set(criterion_ids)) != len(criterion_ids):
        raise ValueError("Each acceptance clause must appear exactly once.")
    expected_ids = {clause["id"] for clause in acceptance_clauses}
    if set(criterion_ids) - expected_ids:
        raise ValueError("Review plan references an unknown acceptance clause.")
    if set(criterion_ids) != expected_ids:
        raise ValueError("Review plan must cover every root acceptance clause.")
    return normalized


def validate_root_assessments(
    plan: list[dict[str, str]], decision: str, raw_assessments: object
) -> tuple[list[dict[str, Any]], str]:
    """Return normalized criterion assessments and derived assurance."""
    if not isinstance(raw_assessments, list) or not raw_assessments:
        raise ValueError("Root review requires one criterion assessment per check.")
    assessments = [_validate_assessment(item) for item in raw_assessments]
    expected_ids = {check["criterion_id"] for check in plan}
    assessment_ids = [item["criterion_id"] for item in assessments]
    if len(set(assessment_ids)) != len(assessment_ids):
        raise ValueError("Each root criterion must be assessed exactly once.")
    if set(assessment_ids) != expected_ids:
        raise ValueError("Criterion assessments must cover every review check.")

    plan_by_id = {check["criterion_id"]: check for check in plan}
    for assessment in assessments:
        testability = plan_by_id[assessment["criterion_id"]]["testability"]
        result = assessment["result"]
        evidence_ids = assessment["evidence_ids"]
        if testability == "empirical":
            if result == "judgment_only":
                raise ValueError("Empirical criteria cannot use judgment-only review.")
            if result == "supported" and not evidence_ids:
                raise ValueError("Empirical support requires evidence references.")
            if decision == "approved" and result != "supported":
                raise ValueError(
                    "ResultReviewer cannot approve contradicted or inconclusive "
                    "empirical criteria."
                )
        elif result == "judgment_only":
            if evidence_ids:
                raise ValueError("Judgment-only assessments cannot cite evidence.")
        elif decision == "approved":
            raise ValueError("Judgment criteria require judgment-only assessment.")
    return assessments, _derive_assurance(plan, assessments)


def _validate_assessment(value: object) -> dict[str, Any]:
    """Return one normalized criterion assessment."""
    if not isinstance(value, dict) or set(value) != _ASSESSMENT_FIELDS:
        raise ValueError("Each criterion assessment has unknown or missing fields.")
    criterion_id = value["criterion_id"]
    result = value["result"]
    evidence_ids = value["evidence_ids"]
    inference = value["inference"]
    limitations = value["limitations"]
    if not isinstance(criterion_id, str) or not criterion_id.strip():
        raise ValueError("Criterion assessment ID must be a non-empty string.")
    if result not in _ASSESSMENT_RESULTS:
        raise ValueError("Criterion assessment result is invalid.")
    if (
        not isinstance(evidence_ids, list)
        or any(not isinstance(item, str) or not item.strip() for item in evidence_ids)
        or len(set(evidence_ids)) != len(evidence_ids)
    ):
        raise ValueError("Criterion assessment evidence IDs are invalid.")
    if not isinstance(inference, str) or not inference.strip():
        raise ValueError("Criterion assessment inference is required.")
    if not isinstance(limitations, str) or not limitations.strip():
        raise ValueError("Criterion assessment limitations are required.")
    return {
        "criterion_id": criterion_id.strip(),
        "result": result,
        "evidence_ids": [item.strip() for item in evidence_ids],
        "inference": inference.strip(),
        "limitations": limitations.strip(),
    }


def _derive_assurance(
    plan: list[dict[str, str]], assessments: list[dict[str, Any]]
) -> str:
    """Derive assurance without treating Reviewer judgment as proof."""
    results = {item["result"] for item in assessments}
    testabilities = {check["testability"] for check in plan}
    if "contradicted" in results:
        return "contradicted"
    if "inconclusive" in results:
        return "inconclusive"
    if testabilities == {"empirical"}:
        return "observed"
    if testabilities == {"judgment"}:
        return "judgment_only"
    return "mixed"


def retain_reviewed_result_revision(task: Any, event: dict[str, Any]) -> None:
    """Retain the reviewed result revision identity on the task (FR-009).

    The exact report behind an earlier verdict stays identifiable after the
    active ``result`` is replaced by a later execution.
    """
    anchor = event.get("result_revision")
    if (
        isinstance(anchor, dict)
        and anchor.get("revision_id")
        and anchor["revision_id"]
        not in {item["revision_id"] for item in task.result_revisions}
    ):
        task.result_revisions.append(
            {
                "revision_id": anchor["revision_id"],
                "content_hash": anchor["content_hash"],
            }
        )


def attach_runtime_anchor(event: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Attach trusted runtime result/artifact identities when present."""
    if runtime_anchor := validate_runtime_revision_anchor(
        metadata.get("runtime_result_revision")
    ):
        event["result_revision"] = runtime_anchor


def cumulative_progress_entries(store: Any) -> list[dict[str, Any]]:
    """Return goal-ordered immutable progress entries from committed reviews.

    Walks the store's global transition log (append-only across tasks) so
    sibling and replanned reviews keep their original goal order. Each entry
    is derived from one committed review event; nothing here can erase an
    earlier entry. Replan boundaries are not committed review events and are
    excluded naturally.
    """
    entries: list[dict[str, Any]] = []
    for action in store.transition_log:
        if action.get("action") != "record_reviewer_decision":
            continue
        task_id = action.get("task_id")
        task = store.tasks.get(task_id) if task_id else None
        if task is None:
            continue
        event_id = action.get("review_event_id")
        event = next(
            (
                item
                for item in task.reviewer_decisions
                if item.get("event_id") == event_id
            ),
            None,
        )
        if event is None:
            continue
        entries.append(_progress_entry(task, event))
    return entries


def _progress_entry(task: Any, event: dict[str, Any]) -> dict[str, Any]:
    """Build one immutable progress entry from a committed review event."""
    anchor = event.get("result_revision")
    return {
        "task_id": task.task_id,
        "task_title": task.title,
        "event_id": event.get("event_id"),
        "decision": event.get("decision"),
        "review_summary": event.get("review_summary", ""),
        "result_hash": (anchor or {}).get("content_hash"),
        "artifact_range": (anchor or {}).get("artifact_range"),
        "anchored": isinstance(anchor, dict),
    }


def render_progress_report(
    store: Any, *, limit: int = 8, decisions: set[str] | None = None
) -> str:
    """Render the bounded reviewer-owned cumulative progress projection.

    Read-only: every worker role receives this derived report; only
    ResultReviewer can append new entries through ``task_review_decision``.
    Role projections default to approved-only accepted knowledge so
    task-local rejection/postponement detail stays in the task journal.
    """
    entries = cumulative_progress_entries(store)
    if decisions is not None:
        entries = [entry for entry in entries if entry["decision"] in decisions]
    entries = entries[-limit:]
    if not entries:
        return ""
    lines = [
        "## Cumulative progress (reviewer-owned, append-only)",
        "Earlier committed verdicts are immutable; do not repeat or undo them.",
    ]
    for entry in entries:
        summary = str(entry["review_summary"]).strip()
        if len(summary) > 120:
            summary = f"{summary[:117]}..."
        if entry["anchored"]:
            result = f"result={entry['result_hash'][:12]}"
            artifact_range = entry["artifact_range"] or {}
            artifact = (
                f"artifacts={artifact_range['from'][:12]}..{artifact_range['to'][:12]}"
            )
        else:
            result = "result=unanchored"
            artifact = "artifacts=unanchored"
        lines.append(
            f"- [{entry['decision']}] {entry['task_title']} "
            f"({entry['event_id']}): {summary} | {result} | {artifact}"
        )
    return "\n".join(lines)
