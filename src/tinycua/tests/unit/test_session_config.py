"""Tests for SessionConfig dataclass."""

from tinycua.config.session_config import SessionConfig


def test_session_config_defaults():
    """SessionConfig has sensible defaults."""
    config = SessionConfig()
    assert config.compaction_strategy is None
    assert config.max_context_messages == 100
    assert config.max_context_tokens is None
    assert config.metadata == {}


def test_session_config_custom_values():
    """SessionConfig accepts custom values."""
    config = SessionConfig(
        compaction_strategy="sliding_window",
        max_context_messages=50,
        max_context_tokens=8000,
        metadata={"key": "value"},
    )
    assert config.compaction_strategy == "sliding_window"
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
