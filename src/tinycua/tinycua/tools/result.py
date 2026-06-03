"""Native tool result model.

Provides ``ToolResult``, a structured dataclass for all tool executions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Structured result from any tool execution.

    Attributes:
        success: True if tool completed without error.
        output: Primary output (stdout, file content, etc.).
        error: Error message if execution failed.
        metadata: Extra info: exit_code, timed_out, chars_written, etc.
        duration: Execution duration in seconds.
    """

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation.

        Returns:
            A dictionary with all ToolResult fields.
        """
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "duration": self.duration,
        }
