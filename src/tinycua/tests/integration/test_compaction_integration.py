"""Integration tests for CompactionStrategy (Milestone 1.3)."""

from unittest.mock import MagicMock, patch

import pytest

from tinycua.compaction.errors import CompactionError
from tinycua.compaction.simple import SimpleCompaction
from tinycua.compaction.strategy import CompactionStrategy
from tinycua.config.session_config import SessionConfig
from tinycua.models.session import Session


class TestCompactionStrategyContract:
    """Verify the CompactionStrategy ABC enforces the contract."""

    def test_compaction_strategy_is_abstract(self):
        """CompactionStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CompactionStrategy()

    def test_compaction_strategy_requires_compact(self):
        """Subclass without compact() cannot be instantiated."""

        class IncompleteStrategy(CompactionStrategy):
            pass

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_concrete_strategy_compact_returns_assistant_message(self):
        """A valid strategy returns exactly one assistant-role message."""

        class DummyStrategy(CompactionStrategy):
            def compact(self, messages):
                return {"role": "assistant", "content": "summary"}

        strategy = DummyStrategy()
        result = strategy.compact([{"role": "user", "content": "hello"}])
        assert result == {"role": "assistant", "content": "summary"}


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


class TestSessionCompactContext:
    """Verify Session.compact_context() integration with strategy."""

    def test_compact_context_returns_none_when_no_strategy(self):
        """compact_context() returns None when no strategy configured."""
        session = Session()
        result = session.compact_context()
        assert result is None

    def test_compact_context_delegates_to_strategy(self):
        """compact_context() calls the configured strategy."""
        strategy = SimpleCompaction()
        session = Session(
            session_config=SessionConfig(compaction_strategy=strategy)
        )
        session.session_context = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

        with patch.object(strategy, "compact") as mock_compact:
            mock_compact.return_value = {"role": "assistant", "content": "summary"}
            result = session.compact_context()

        assert result == {"role": "assistant", "content": "summary"}
        mock_compact.assert_called_once()

    def test_compact_context_with_explicit_window(self):
        """compact_context(window=...) uses the provided window."""
        strategy = SimpleCompaction()
        session = Session(
            session_config=SessionConfig(compaction_strategy=strategy)
        )
        window = [{"role": "user", "content": "subset"}]

        with patch.object(strategy, "compact") as mock_compact:
            mock_compact.return_value = {
                "role": "assistant",
                "content": "subset summary",
            }
            result = session.compact_context(window=window)

        mock_compact.assert_called_once_with(window)
        assert result["content"] == "subset summary"


class TestFactoryIntegration:
    """Verify factory creates SimpleCompaction with parent config."""

    # Known limitation: factory integration is deferred to Phase 2.
    # Config-passing to SimpleCompaction is validated by
    # test_simple_compaction_uses_parent_config (unit test).

    @patch("tinycua.factory.create_tinycua_agent")
    def test_factory_initializes_simple_compaction(self, mock_create):
        """create_tinycua_agent() initializes SimpleCompaction with parent config."""
        from tinycua.factory import create_tinycua_agent

        strategy = SimpleCompaction()
        config = SessionConfig(compaction_strategy=strategy)
        mock_create.return_value = MagicMock(
            loop=MagicMock(session_config=config)
        )
        agent = create_tinycua_agent(session_config=config)
        mock_create.assert_called_once_with(session_config=config)
        assert agent.loop.session_config.compaction_strategy is strategy
