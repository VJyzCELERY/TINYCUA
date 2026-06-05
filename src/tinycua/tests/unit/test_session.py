"""Tests for Session model."""

from tinycua.config.session_config import SessionConfig
from tinycua.models.session import Session


def test_session_has_uuid():
    """Session generates a UUID by default."""
    session = Session()
    assert session.session_id is not None
    assert len(session.session_id) == 36  # UUID format


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


def test_compact_context_is_noop():
    """compact_context() does not raise (placeholder)."""
    session = Session()
    session.compact_context()  # Should not raise
