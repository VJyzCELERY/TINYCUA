"""Result models for runner execution."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A tool call that was made."""

    id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None


@dataclass
class RunResult:
    """Result from a runner execution."""

    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None

    @property
    def total_tokens(self) -> int:
        """Get total token count."""
        return self.usage.get("total_tokens", 0)

    @property
    def input_tokens(self) -> int:
        """Get input token count."""
        return self.usage.get("input_tokens", 0)

    @property
    def output_tokens(self) -> int:
        """Get output token count."""
        return self.usage.get("output_tokens", 0)


