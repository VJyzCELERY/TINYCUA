"""Unit tests for the node_guidance module (reviewer guidance extraction)."""

from __future__ import annotations

from tinycua.loops.node_guidance import (
    _RESULT_REVIEWER_CONTINUATION,
    _RESULT_REVIEWER_INSTRUCTION,
    build_reviewer_tool_guidance,
)


class TestNodeGuidanceModule:
    """The node_guidance module exports reviewer guidance correctly."""

    def test_instruction_importable(self):
        assert _RESULT_REVIEWER_INSTRUCTION
        assert "ResultReviewer" in _RESULT_REVIEWER_INSTRUCTION

    def test_instruction_requests_a_free_form_report(self):
        instruction = _RESULT_REVIEWER_INSTRUCTION.lower()

        assert "report" in instruction
        assert "validation evidence" not in instruction
        assert "[validated]" not in instruction

    def test_instruction_under_950_chars(self):
        # The incremental-review/transient-revalidation contract sentence
        # (cumulative-review-artifact-history) raised the terse single-paragraph
        # ceiling; 1120 still rejects phase-essay bloat.
        assert len(_RESULT_REVIEWER_INSTRUCTION) < 1120

    def test_continuation_importable(self):
        assert _RESULT_REVIEWER_CONTINUATION
        assert "evidence-backed active-task conclusion" in _RESULT_REVIEWER_CONTINUATION
        assert "mandatory when reviewing the root" in _RESULT_REVIEWER_CONTINUATION


class TestBuildReviewerToolGuidance:
    """build_reviewer_tool_guidance returns guidance keyed on present tools."""

    def test_returns_string_when_tools_present(self):
        class _FakeTool:
            def __init__(self, name: str) -> None:
                self.name = name

        tools = [_FakeTool("run_shell"), _FakeTool("task_review_decision")]
        result = build_reviewer_tool_guidance(tools)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Tool guidance:" in result

    def test_returns_empty_when_no_tools(self):
        result = build_reviewer_tool_guidance(None)
        assert result == ""
