"""Unit tests for SimpleCompaction."""

from unittest.mock import MagicMock, patch

import pytest

from tinycua.compaction.errors import CompactionError
from tinycua.compaction.simple import SimpleCompaction


class TestSimpleCompaction:
    """Verify SimpleCompaction behavior with mocked Agent."""

    def test_simple_compaction_returns_assistant_message(self):
        """SimpleCompaction.compact() returns one assistant-role message."""
        strategy = SimpleCompaction()
        messages = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "And 3+3?"},
        ]

        with patch.object(
            strategy, "_run_compaction_agent", new_callable=MagicMock
        ) as mock_run:
            mock_run.return_value = (
                "The session covered basic arithmetic: 2+2=4 and 3+3=6."
            )
            result = strategy.compact(messages)

        assert result["role"] == "assistant"
        assert "arithmetic" in result["content"]

    def test_simple_compaction_toolless(self):
        """SimpleCompaction creates Agent with no tools."""
        strategy = SimpleCompaction()
        assert strategy.tools == []

    def test_simple_compaction_uses_parent_config(self):
        """SimpleCompaction inherits model/provider from parent config."""
        parent_config = {"model": "gpt-4", "provider": "openai"}
        strategy = SimpleCompaction(parent_config=parent_config)
        assert strategy.parent_config == parent_config

    def test_simple_compaction_fallback_config(self):
        """SimpleCompaction uses fallback when no parent config."""
        strategy = SimpleCompaction()
        assert strategy.parent_config is None
        assert strategy.fallback_config is not None
        assert "model" in strategy.fallback_config
        assert "provider" in strategy.fallback_config

    def test_simple_compaction_empty_message_list(self):
        """compact() with empty message list returns assistant message."""
        strategy = SimpleCompaction()
        with patch.object(
            strategy, "_run_compaction_agent", new_callable=MagicMock
        ) as mock_run:
            mock_run.return_value = ""
            result = strategy.compact([])

        assert result["role"] == "assistant"
        assert isinstance(result["content"], str)

    def test_simple_compaction_agent_unreachable_raises_compaction_error(self):
        """CompactionError raised when Agent is unreachable."""
        strategy = SimpleCompaction()
        messages = [{"role": "user", "content": "hello"}]
        with patch.object(
            strategy,
            "_run_compaction_agent",
            side_effect=CompactionError("Agent unreachable"),
        ):
            with pytest.raises(CompactionError, match="Agent unreachable"):
                strategy.compact(messages)

    def test_simple_compaction_internal_failure_raises_compaction_error(self):
        """CompactionError raised on internal failure."""
        strategy = SimpleCompaction()
        with patch.object(
            strategy,
            "_run_compaction_agent",
            side_effect=CompactionError("Compaction failed"),
        ):
            with pytest.raises(CompactionError):
                strategy.compact([{"role": "user", "content": "test"}])

    def test_simple_compaction_wraps_unknown_exception(self):
        """Non-CompactionError exceptions are wrapped in CompactionError."""
        strategy = SimpleCompaction()
        with patch.object(
            strategy,
            "_run_compaction_agent",
            side_effect=RuntimeError("unexpected failure"),
        ):
            with pytest.raises(CompactionError, match="Compaction failed"):
                strategy.compact([{"role": "user", "content": "test"}])
