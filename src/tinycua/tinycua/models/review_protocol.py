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
