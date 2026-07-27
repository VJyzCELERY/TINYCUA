"""QueryAnalyst context-summary tool contracts."""

from __future__ import annotations

from tinycua.tools.query_context_summary import QueryContextSummaryTool


def test_summarize_query_context_accepts_a_concise_summary() -> None:
    """The tool commits the neutral high-level request summary."""
    result = QueryContextSummaryTool()(context_summary="Continue the migration plan.")

    assert result == {
        "success": True,
        "context_summary": "Continue the migration plan.",
    }


def test_summarize_query_context_rejects_missing_summary() -> None:
    """A route cannot proceed without a usable preliminary summary."""
    result = QueryContextSummaryTool()(context_summary=" ")

    assert result["success"] is False
