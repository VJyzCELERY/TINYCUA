"""Structured digest output tool stub for TinyCUA nodes.

Provides DigestInformationTool for producing structured digest output.
"""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool


class DigestInformationTool(Tool):
    """Tool stub for producing structured digest output.

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

        Returns:
            A dict containing the structured digest.
        """
        return {
            "digest": information,
            "format": "structured",
        }
