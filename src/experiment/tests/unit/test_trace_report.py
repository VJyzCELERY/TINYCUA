"""Unit tests for the trace_report generator's rendering logic."""

from __future__ import annotations

import trace_report


def _summary(exp: int, **overrides) -> dict:
    base = {
        "llm_calls": 1,
        "in_tokens": 100,
        "out_tokens": 10,
        "total_tokens": 110,
        "by_node": {
            "ResultReviewer": {"calls": 1, "total_tokens": 50},
        },
        "review_verdicts": {
            "approved": 1,
            "needs_revision": 0,
            "rejected": 0,
            "replan": 0,
        },
        "task_rework_counts": {},
        "defect_signals": {
            "multi_decision_reviewer_session": 0,
            "triple_needs_revision_task": 0,
            "non_zero_shell": 0,
            "oversize_listing": 0,
            "session_without_terminate": 0,
        },
        "defect_session_count": 0,
        "total_sessions": 1,
        "architectural_tokens": 60,
        "prototype_defect_tokens": 50,
        "reviewer_causes": [],
        "task_stories": {},
        "metadata": {"duration_seconds": 10.0},
        "_exp": exp,
        "_task_label": "test task",
        "_stdout_path": "fake/path/stdout.txt",
    }
    base.update(overrides)
    return base


def test_render_trace_evidence_lists_per_experiment_aggregate() -> None:
    out = trace_report.render_trace_evidence_report([_summary(4)])
    assert "Per-experiment aggregate" in out
    assert "Notion" not in out  # default test label is "test task"
    assert "0/0/0/0" not in out  # the verdict summary for synthetic shows 1/0/0/0


def test_render_architectural_report_emits_split_and_signal_catalog() -> None:
    out = trace_report.render_architectural_vs_prototype_report([_summary(4)])
    assert "Strict signal catalog" in out
    assert "Architectural-inherent" in out
    assert (
        "28.3%" not in out
    )  # single-experiment aggregate differs from the real 5-run number
    assert "test task" in out  # the table includes the synthetic task label
    # Each documented signal is named verbatim.
    for signal in [
        "multi_decision_reviewer_session",
        "triple_needs_revision_task",
        "non_zero_shell",
        "oversize_listing",
        "session_without_terminate",
    ]:
        assert signal in out


def test_render_reviewer_ablation_report_states_methodology_assumptions() -> None:
    out = trace_report.render_reviewer_ablation_report([_summary(4)])
    # The three lines that make the retrospective ablation defensible to reviewers.
    assert "trace-based / retrospective ablation" in out
    assert "auto-accept the executor's first recorded task_result" in out
    assert "second-order effects" in out
    # Reviewer cost row should be present.
    assert "Reviewer LLM calls" in out


def test_false_approval_detector_flags_admitted_wrong_approval() -> None:
    summary = _summary(
        4,
        reviewer_causes=[
            {
                "seq": 100,
                "task_id": "t SQLITE",
                "decision": "approved",
                "status": "completed",
                "cited_cause": "unclassified",
                "preceding_text": "Code looks fine, approving.",
            },
            {
                "seq": 101,
                "task_id": "t SQLITE",
                "decision": "needs_revision",
                "status": "in_progress",
                "cited_cause": "type_error",
                "preceding_text": "I should NOT have approved this, the code is broken.",
            },
        ],
    )
    results = trace_report._find_false_approvals([summary])
    assert results, (
        "the detector must catch an approval immediately followed by an admitted-wrong reversal"
    )
    assert results[0]["seq"] == 100


def test_worked_example_renders_when_task_story_has_rework_count() -> None:
    summary = _summary(
        4,
        task_rework_counts={"64c789e203a34b4caa12d711a94eea56": 5},
        task_stories={
            "64c789e203a34b4caa12d711a94eea56": {
                "task_id": "64c789e203a34b4caa12d711a94eea56",
                "rework_count": 5,
                "timeline": [
                    {
                        "seq": 1,
                        "kind": "tool_result",
                        "actor": "ResultReviewer",
                        "tool": "task_review_decision",
                        "decision": "needs_revision",
                        "status": "in_progress",
                    },
                    {
                        "seq": 2,
                        "kind": "tool_result",
                        "actor": "ResultReviewer",
                        "tool": "task_review_decision",
                        "decision": "approved",
                        "status": "completed",
                    },
                ],
            }
        },
        reviewer_causes=[
            {
                "seq": 1,
                "task_id": "64c789e203a34b4caa12d711a94eea56",
                "decision": "needs_revision",
                "status": "in_progress",
                "cited_cause": "syntax_error",
                "preceding_text": "syntax error",
            },
        ],
    )
    out = trace_report.render_architectural_vs_prototype_report([summary])
    assert "Worked example" in out
    assert "64c789e2" in out


def test_openname_cross_harness_section_lists_parent_tool_inventory() -> None:
    # Function is hermetic: builds the table from whatever OpenCode stdout the
    # repo currently has; we only assert the table headers render and the
    # defensible-by-line-number claim is present.
    out = trace_report._opencode_cross_harness_section()
    assert "Orchestrator tool_use tools" in out
    assert "successfully created the complete Notion-like application" in out
    assert "session" in out and "not persisted" in out
