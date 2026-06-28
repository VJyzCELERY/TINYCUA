"""Unit tests for CompactionStrategy ABC contract."""

import pytest

from tinycua.compaction.strategy import CompactionStrategy


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

    def test_compact_signature_accepts_list_of_dicts(self):
        """compact() accepts list[dict] and returns dict."""

        class SigStrategy(CompactionStrategy):
            def compact(self, messages):
                return {"role": "assistant", "content": f"{len(messages)} messages"}

        strategy = SigStrategy()
        messages = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        result = strategy.compact(messages)
        assert isinstance(result, dict)
        assert result["role"] == "assistant"
        assert "2 messages" in result["content"]
