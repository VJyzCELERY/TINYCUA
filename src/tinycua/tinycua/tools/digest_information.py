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
        super().__init__(name="digest_information")

    def __call__(
        self,
        information: str = "",
        **kwargs: Any,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Produce a structured digest from the given information.

        Args:
            information: The raw information to digest.
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            A dict containing the structured digest.
        """
        lines = [line.strip() for line in information.splitlines() if line.strip()]
        key_points = [
            line.lstrip("-*•0123456789. )")
            for line in lines
            if line.startswith(("-", "*", "•")) or line[:1].isdigit()
        ]
        constraints = [
            line
            for line in lines
            if any(term in line.lower() for term in {"must", "never", "constraint", "require"})
        ]
        summary = " ".join(lines[:2])[:800]
        return {
            "summary": summary,
            "key_points": key_points[:10],
            "constraints": constraints[:10],
            "source_length": len(information),
            "format": "structured_digest",
        }
