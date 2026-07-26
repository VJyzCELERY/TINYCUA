"""System prompt building for TinyCUA nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


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
    metadata: dict[str, Any] = field(default_factory=dict)


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

    def add_static(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a static prompt fragment.

        Args:
            content: The static prompt text.
            metadata: Optional metadata for this fragment.
        """
        self.fragments.append(
            SystemPrompt(
                priority=self._next_priority(),
                kind="static",
                content=content,
                metadata=metadata or {},
            )
        )

    def add_configurable_append(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Add a configurable append prompt fragment.

        Args:
            content: The configurable append text.
            metadata: Optional metadata for this fragment.
        """
        self.fragments.append(
            SystemPrompt(
                priority=self._next_priority(),
                kind="configurable",
                content=content,
                metadata=metadata or {},
            )
        )

    def add_dynamic_context(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Add a dynamic context prompt fragment.

        Args:
            content: The dynamic context text.
            metadata: Optional metadata for this fragment.
        """
        self.fragments.append(
            SystemPrompt(
                priority=self._next_priority(),
                kind="dynamic",
                content=content,
                metadata=metadata or {},
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


def build_runtime_context(
    now: datetime | None = None,
    *,
    date_snapshot: str | None = None,
    env_snapshot: str | None = None,
    workspace_dir: Any = None,
) -> str:
    """Build a STABLE runtime context label for node system prompts.

    Deliberately does NOT include a per-call timestamp: a ``datetime.now()``
    in the system message guarantees zero prompt-cache hits on every provider
    (llama.cpp KV reuse, OpenAI prefix caching). The current time-of-day moves
    to the last USER message instead (see Node.build_messages) so the system
    prefix stays byte-stable across calls in a session.

    When ``date_snapshot`` is provided (a session-scoped ``YYYY-MM-DD (Weekday)``
    string taken once at session start), it is included in the stable system
    context as ``Today: <snapshot>``. The snapshot is stable for the session
    lifetime, so FR-015 prompt-cache stability is preserved within a session
    while still giving the model an authoritative current date in the system
    prompt (instead of only in volatile user-context metadata).

    ``env_snapshot`` is the session-scoped environment block (OS, shell, python,
    virtualization) — also stable for the session. ``workspace_dir`` is the
    session's workspace path (where file tools operate), rendered when set.

    The ``now`` arg is accepted for backward-compat/test purposes but ignored
    — the context is constant within a session.
    """
    del now  # stability by design; see docstring
    parts = ["## Runtime Context", "Agent runtime: TinyCUA"]
    if date_snapshot:
        parts.append(f"Today: {date_snapshot}")
        parts.append(
            "Today is the authoritative reference for the current date. Your "
            "training data and knowledge cutoff are not evidence of what is true "
            "today. Treat claims about the current state of the world as unknown "
            "until verified with available evidence. If verification is unavailable, "
            "state the uncertainty instead of guessing."
        )
    if env_snapshot:
        parts.append(env_snapshot)
    if workspace_dir is not None:
        parts.append(
            f"Workspace: {workspace_dir} (file tools operate here; write outputs here)"
        )
    return "\n".join(parts)
