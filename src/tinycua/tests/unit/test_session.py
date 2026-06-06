"""Tests for Session model."""

from unittest.mock import patch

from tinycua.compaction.simple import SimpleCompaction
from tinycua.config.session_config import SessionConfig
from tinycua.models.session import Session


def test_session_has_uuid():
    """Session generates a UUID by default."""
    session = Session()
    assert session.session_id is not None
    assert len(session.session_id) == 32  # UUID hex format (no dashes)


def test_session_unique_ids():
    """Each session gets a unique ID."""
    a = Session()
    b = Session()
    assert a.session_id != b.session_id


def test_session_defaults():
    """Session has sensible defaults."""
    session = Session()
    assert session.parent_id is None
    assert session.session_config is None
    assert session.chat_history == []
    assert session.session_context == []
    assert session.task is None
    assert session.todo == []


def test_session_with_parent():
    """Session accepts a parent_id."""
    parent = Session()
    child = Session(parent_id=parent.session_id)
    assert child.parent_id == parent.session_id


def test_session_with_config():
    """Session accepts a SessionConfig."""
    config = SessionConfig(max_context_messages=50)
    session = Session(session_config=config)
    assert session.session_config is config
    assert session.session_config.max_context_messages == 50


def test_compact_context_returns_none_when_no_strategy():
    """compact_context() returns None when no strategy configured."""
    session = Session()
    result = session.compact_context()
    assert result is None


def test_compact_context_delegates_to_strategy():
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


def test_compact_context_with_explicit_window():
    """compact_context(window=...) uses the provided window."""
    strategy = SimpleCompaction()
    session = Session(
        session_config=SessionConfig(compaction_strategy=strategy)
    )
    window = [{"role": "user", "content": "subset"}]

    with patch.object(strategy, "compact") as mock_compact:
        mock_compact.return_value = {"role": "assistant", "content": "subset summary"}
        result = session.compact_context(window=window)

    mock_compact.assert_called_once_with(window)
    assert result["content"] == "subset summary"
