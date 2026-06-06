"""System prompt building for TinyCUA nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class SystemPrompt:
    """A single prompt fragment with priority and kind.

    Attributes:
        priority: Ordering priority (lower = earlier in merged content).
        kind: Type of prompt fragment.
        content: The prompt text.
        metadata: Arbitrary metadata for this fragment.
    """

    priority: int
    kind: Literal["static", "configurable", "dynamic"]
    content: str
    metadata: dict = field(default_factory=dict)


class SystemPromptBuilder:
    """Assembles fragments into a single system-role message.

    Fragments are ordered by explicit priority, then merged into one string.
    """

    def __init__(self) -> None:
        """Initialize the builder with an empty fragment list."""
        self.fragments: list[SystemPrompt] = []
        self._priority_counter = 0

    def _next_priority(self) -> int:
        """Get next priority value."""
        priority = self._priority_counter
        self._priority_counter += 1
        return priority

    def add_static(self, content: str) -> None:
        """Add a static prompt fragment.

        Args:
            content: The static prompt text.
        """
        self.fragments.append(
            SystemPrompt(
                priority=self._next_priority(),
                kind="static",
                content=content,
            )
        )

    def add_configurable_append(self, content: str) -> None:
        """Add a configurable append prompt fragment.

        Args:
            content: The configurable append text.
        """
        self.fragments.append(
            SystemPrompt(
                priority=self._next_priority(),
                kind="configurable",
                content=content,
            )
        )

    def add_dynamic_context(self, content: str) -> None:
        """Add a dynamic context prompt fragment.

        Args:
            content: The dynamic context text.
        """
        self.fragments.append(
            SystemPrompt(
                priority=self._next_priority(),
                kind="dynamic",
                content=content,
            )
        )

    def build(self) -> dict[str, str]:
        """Build a single system-role message from fragments.

        Fragments are sorted by priority (stable sort preserves insertion order
        for equal priorities), then merged into one string with newlines.

        Returns:
            Dictionary with "role" and "content" keys.
        """
        if not self.fragments:
            return {"role": "system", "content": ""}

        # Sort by priority (stable sort)
        sorted_fragments = sorted(self.fragments, key=lambda f: f.priority)

        # Merge content
        merged_content = "\n".join(f.content for f in sorted_fragments)

        return {"role": "system", "content": merged_content}
