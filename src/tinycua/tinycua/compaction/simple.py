"""SimpleCompaction default implementation.

Milestone 8 Stream B: upgraded to support LLM-based compaction via an async
callable. When ``llm_call`` is provided, ``compact()`` makes an async LLM
call to summarize the content. When ``llm_call`` is None (tests, offline),
falls back to the deterministic local summarizer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tinycua.compaction.errors import CompactionError
from tinycua.compaction.strategy import CompactionStrategy


class SimpleCompaction(CompactionStrategy):
    """Default compaction strategy with optional LLM-based summarization.

    Args:
        parent_config: Optional dict with ``model`` and ``provider`` keys
            copied from the parent session config.
        fallback_config: Optional override for the fallback config.
        llm_call: Optional async callable that takes a list of messages and
            returns a summary string. When provided, ``compact()`` makes an
            async LLM call to summarize. When None, falls back to the
            deterministic local summarizer.
    """

    _FALLBACK_CONFIG: dict[str, Any] = {
        "model": "gpt-4o-mini",
        "provider": "openai",
    }

    _COMPACTION_SYSTEM_PROMPT = (
        "You are a context compaction agent. Summarize the following content "
        "concisely, preserving task-relevant facts, constraints, identifiers, "
        "decisions, evidence, unresolved issues, and actionable conclusions. "
        "Do not add new information. "
        "Output only the summary — no preamble, no meta-commentary."
    )

    def __init__(
        self,
        parent_config: dict[str, Any] | None = None,
        fallback_config: dict[str, Any] | None = None,
        llm_call: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
    ) -> None:
        """Initialize SimpleCompaction.

        Args:
            parent_config: Optional dict with ``model`` and ``provider`` keys.
            fallback_config: Optional override for the fallback config.
            llm_call: Optional async LLM callable for summarization.
        """
        self._parent_config = parent_config
        self._fallback_config = fallback_config or self._FALLBACK_CONFIG.copy()
        self._llm_call = llm_call

    @property
    def tools(self) -> list[Any]:
        """Return the compaction Agent's tool list (empty for SimpleCompaction)."""
        return []

    @property
    def parent_config(self) -> dict[str, Any] | None:
        """Return the parent config snapshot."""
        return self._parent_config

    @property
    def fallback_config(self) -> dict[str, Any]:
        """Return the fallback model/provider config."""
        return self._fallback_config

    async def compact(self, messages: list[dict]) -> dict:
        """Compact messages into one assistant-role summary.

        When ``llm_call`` is set, makes an async LLM call to summarize.
        Otherwise, falls back to the deterministic local summarizer.

        Args:
            messages: The conversation messages to compact.

        Returns:
            A dict with ``role`` set to ``"assistant"`` and ``content``
            containing the compacted summary.

        Raises:
            CompactionError: If compaction fails.
        """
        try:
            if self._llm_call is not None:
                summary = await self._run_llm_compaction(messages)
            else:
                summary = self._run_local_compaction(messages)
            return {"role": "assistant", "content": summary}
        except CompactionError:
            raise
        except Exception as exc:
            raise CompactionError(f"Compaction failed: {exc}") from exc

    async def _run_llm_compaction(self, messages: list[dict]) -> str:
        """Run an LLM-based compaction call.

        Args:
            messages: The messages to summarize.

        Returns:
            The LLM-generated summary string.
        """
        # Build the compaction prompt: system + user with all content.
        content_parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", "")).strip()
            if content:
                content_parts.append(f"[{role}] {content}")
        if not content_parts:
            return ""
        user_content = "\n\n".join(content_parts)
        compaction_messages = [
            {"role": "system", "content": self._COMPACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        result = await self._llm_call(compaction_messages)
        return str(result).strip()

    def _run_local_compaction(self, messages: list[dict]) -> str:
        """Create a deterministic tool-less summary (fallback for tests/offline).

        Args:
            messages: The messages to compact.

        Returns:
            The summary string.
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", "")).strip().replace("\n", " ")
            if content:
                parts.append(f"{role}: {content}")
        if not parts:
            return ""
        return "Compacted conversation summary:\n" + "\n".join(parts[-20:])
