"""Tests for SessionConfig dataclass."""

from tinycua.compaction.simple import SimpleCompaction
from tinycua.config.session_config import SessionConfig


def test_session_config_defaults():
    """SessionConfig has sensible defaults."""
    config = SessionConfig()
    assert config.compaction_strategy is None
    assert config.max_context_messages == 100
    assert config.max_context_tokens is None
    assert config.metadata == {}
    assert config.enable_open_question_review is False


def test_session_config_custom_values():
    """SessionConfig accepts custom values."""
    strategy = SimpleCompaction()
    config = SessionConfig(
        compaction_strategy=strategy,
        max_context_messages=50,
        max_context_tokens=8000,
        metadata={"key": "value"},
    )
    assert config.compaction_strategy is strategy
    assert config.max_context_messages == 50
    assert config.max_context_tokens == 8000
    assert config.metadata == {"key": "value"}


def test_session_config_equality():
    """SessionConfig instances with same values are equal."""
    a = SessionConfig(max_context_messages=100)
    b = SessionConfig(max_context_messages=100)
    assert a == b


def test_session_config_inequality():
    """SessionConfig instances with different values are not equal."""
    a = SessionConfig(max_context_messages=100)
    b = SessionConfig(max_context_messages=50)
    assert a != b
