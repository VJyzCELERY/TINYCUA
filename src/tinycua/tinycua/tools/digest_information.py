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
                "Commit broad orientation for downstream planning. Anchors and "
                "advice are non-binding; the runtime preserves the original query."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "context_summary": {
                        "type": "string",
                        "description": "Broad orientation map, not a solution or completion report.",
                    },
                    "key_points": {
                        "type": "array",
                        "description": "Non-binding orientation anchors, not proof.",
                        "items": {"type": "string"},
                    },
                    "advisory_instructions": {
                        "type": "array",
                        "description": "Suggested downstream checks, not a binding plan.",
                        "items": {"type": "string"},
                    },
                    "constraints": {
                        "type": "array",
                        "description": "Explicit requirements or verified non-negotiable limits only.",
                        "items": {"type": "string"},
                    },
                    "known_gaps": {
                        "type": "array",
                        "description": "Assumptions downstream must verify before relying on them.",
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
            context_summary: Broad orientation map of gathered context.
            key_points: Non-binding starting anchors for downstream planning.
            advisory_instructions: Suggested checks for downstream nodes.
            constraints: Explicit or verified non-negotiable requirements.
            known_gaps: Assumptions downstream must verify before relying on them.

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
