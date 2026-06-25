"""ToolResult envelope — canonical return shape for hardened tools.

Milestone 6: introduces a consistent dict shape for tool results. Not
retrofitted to all existing tools yet — new and hardened tools use it.
The envelope ensures the loop can reliably check success/error without
per-tool-type inspection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ToolResult:
    """Canonical envelope for tool returns.

    Attributes:
        success: Whether the tool call succeeded.
        output: The tool's output on success (str, dict, list, etc.).
        error: Error message on failure, None on success.
        metadata: Additional structured info (url, content_type, status, etc.).
    """

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize metadata to empty dict if not provided."""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Return as a dict suitable for the tool-result message."""
        return asdict(self)
