"""Structured preliminary-summary tool for QueryAnalyst."""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool


class QueryContextSummaryTool(Tool):
    """Commit QueryAnalyst's neutral summary of the active request context."""

    def __init__(self) -> None:
        super().__init__(
            name="summarize_query_context",
            description=(
                "Commit a concise preliminary summary of what the user wants, "
                "grounded in the provided conversation and session context."
            ),
            parameters={
                "type": "object",
                "properties": {"context_summary": {"type": "string"}},
                "required": ["context_summary"],
                "additionalProperties": False,
            },
        )

    def __call__(self, context_summary: str = "") -> dict[str, Any]:
        """Validate and return the committed preliminary context summary."""
        if not isinstance(context_summary, str) or not context_summary.strip():
            return {"success": False, "error": "context_summary is required"}
        return {"success": True, "context_summary": context_summary.strip()}
