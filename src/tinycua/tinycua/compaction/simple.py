"""SimpleCompaction default implementation."""

from __future__ import annotations

from typing import Any

from tinycua.compaction.errors import CompactionError
from tinycua.compaction.strategy import CompactionStrategy


class SimpleCompaction(CompactionStrategy):
    """Default tool-less compaction Agent implementation.

    Creates a compaction Agent with no tools and a simple summarization
    instruction. Inherits model/provider from a parent config snapshot
    taken at init time, falling back to built-in defaults when no parent
    config is provided.

    Args:
        parent_config: Optional dict with ``model`` and ``provider`` keys
            copied from the parent session config.
        fallback_config: Optional override for the fallback config.
    """

    _FALLBACK_CONFIG: dict[str, Any] = {
        "model": "gpt-4o-mini",
        "provider": "openai",
    }

    def __init__(
        self,
        parent_config: dict[str, Any] | None = None,
        fallback_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize SimpleCompaction.

        Args:
            parent_config: Optional dict with ``model`` and ``provider`` keys.
            fallback_config: Optional override for the fallback config.
        """
        self._parent_config = parent_config
        self._fallback_config = fallback_config or self._FALLBACK_CONFIG.copy()

    @property
    def tools(self) -> list[Any]:
        """Return the compaction Agent's tool list (empty for SimpleCompaction).

        Returns:
            An empty list — SimpleCompaction never uses tools.
        """
        return []

    @property
    def parent_config(self) -> dict[str, Any] | None:
        """Return the parent config snapshot.

        Returns:
            The parent config dict, or None if not provided.
        """
        return self._parent_config

    @property
    def fallback_config(self) -> dict[str, Any]:
        """Return the fallback model/provider config.

        Returns:
            A dict with ``model`` and ``provider`` keys.
        """
        return self._fallback_config

    def compact(self, messages: list[dict]) -> dict:
        """Compact messages into one assistant-role summary.

        Runs a tool-less compaction Agent to produce a summary of the
        conversation history.

        Args:
            messages: The conversation messages to compact.

        Returns:
            A dict with ``role`` set to ``"assistant"`` and ``content``
            containing the compacted summary.

        Raises:
            CompactionError: If the compaction Agent is unreachable or
                returns an error.
        """
        try:
            summary = self._run_compaction_agent(messages)
            return {"role": "assistant", "content": summary}
        except CompactionError:
            raise
        except Exception as exc:
            raise CompactionError(f"Compaction failed: {exc}") from exc

    def _run_compaction_agent(self, messages: list[dict]) -> str:
        """Run the internal compaction Agent (stub).

        In a full implementation this would create an SDK Agent with no
        tools, pass the messages, and return the LLM response content.

        Args:
            messages: The conversation messages to compact.

        Returns:
            The summary string from the compaction Agent.

        Raises:
            CompactionError: If the Agent call fails.
        """
        # Placeholder — real implementation would call the SDK Agent.
        # For now, return a basic concatenation so tests can mock this.
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts) if parts else ""
