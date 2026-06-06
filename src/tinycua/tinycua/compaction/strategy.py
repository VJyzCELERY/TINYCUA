"""CompactionStrategy abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CompactionStrategy(ABC):
    """Abstract base class for context compaction strategies.

    A CompactionStrategy takes a list of messages and returns a single
    assistant-role summary message. Concrete implementations define how
    the compaction is performed (e.g., via an LLM call, rule-based
    summarization, etc.).

    Subclasses MUST implement the ``compact`` method.
    """

    @abstractmethod
    def compact(self, messages: list[dict]) -> dict:
        """Compact a list of messages into a single assistant-role summary.

        Args:
            messages: The conversation messages to compact. Each message is
                a dict with at least ``role`` and ``content`` keys.

        Returns:
            A single dict with ``role`` set to ``"assistant"`` and ``content``
            containing the compacted summary.

        Raises:
            CompactionError: If compaction fails due to Agent unreachability
                or internal errors.
        """
