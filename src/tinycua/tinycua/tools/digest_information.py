"""Structured digest output tool for TinyCUA nodes.

Provides DigestInformationTool for producing structured digest output.
"""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool


class DigestInformationTool(Tool):
    """Tool for producing structured digest output.

    Used by InformationDigesterNode to produce structured digests
    of gathered information for downstream nodes.
    """

    def __init__(self) -> None:
        super().__init__(
            name="digest_information",
            description=(
                "Commit gathered context for downstream planning. The runtime "
                "preserves the original user query separately."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "context_summary": {"type": "string"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "advisory_instructions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "known_gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["context_summary"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        context_summary: str = "",
        key_points: list[str] | None = None,
        advisory_instructions: list[str] | None = None,
        constraints: list[str] | None = None,
        known_gaps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Validate and return a structured digest commit.

        Args:
            context_summary: Concise summary of gathered context.
            key_points: Important facts for downstream planning.
            advisory_instructions: Non-binding guidance for downstream nodes.
            constraints: Constraints discovered while gathering context.
            known_gaps: Material information that remains unavailable.

        Returns:
            The validated digest or a failed commit result.
        """
        if not isinstance(context_summary, str) or not context_summary.strip():
            return {"success": False, "error": "context_summary is required"}
        fields = {
            "key_points": key_points,
            "advisory_instructions": advisory_instructions,
            "constraints": constraints,
            "known_gaps": known_gaps,
        }
        normalized: dict[str, list[str]] = {}
        for name, values in fields.items():
            if values is None:
                normalized[name] = []
            elif not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                return {
                    "success": False,
                    "error": f"{name} must contain non-empty strings",
                }
            else:
                normalized[name] = [value.strip() for value in values]
        return {
            "success": True,
            "context_summary": context_summary.strip(),
            **normalized,
        }
