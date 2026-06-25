"""Tests for Session model."""

from unittest.mock import AsyncMock, patch

import pytest

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


async def test_compact_context_returns_none_when_no_strategy():
    """compact_context() returns None when no strategy configured."""
    session = Session()
    result = await session.compact_context()
    assert result is None


async def test_compact_context_delegates_to_strategy():
    """compact_context() calls the configured strategy."""
    strategy = SimpleCompaction()
    session = Session(session_config=SessionConfig(compaction_strategy=strategy))
    session.session_context = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    with patch.object(strategy, "compact", new=AsyncMock(return_value={"role": "assistant", "content": "summary"})) as mock_compact:
        result = await session.compact_context()

    assert result == {"role": "assistant", "content": "summary"}
    mock_compact.assert_called_once()


async def test_compact_context_with_explicit_window():
    """compact_context(window=...) uses the provided window."""
    strategy = SimpleCompaction()
    session = Session(session_config=SessionConfig(compaction_strategy=strategy))
    window = [{"role": "user", "content": "subset"}]
    session.session_context = list(window) + [
        {"role": "assistant", "content": "after"},
    ]

    with patch.object(strategy, "compact", new=AsyncMock(return_value={"role": "assistant", "content": "subset summary"})) as mock_compact:
        result = await session.compact_context(window=window)

    mock_compact.assert_called_once()
    assert result["content"] == "subset summary"
    assert len(session.session_context) == 2
    assert session.session_context[0].content == "subset summary"
    assert session.session_context[1]["content"] == "after"


async def test_compact_context_empty_window_returns_none():
    """compact_context(window=[]) returns None without calling strategy."""
    strategy = SimpleCompaction()
    session = Session(session_config=SessionConfig(compaction_strategy=strategy))
    session.session_context = [{"role": "user", "content": "hello"}]

    with patch.object(strategy, "compact", new=AsyncMock()) as mock_compact:
        result = await session.compact_context(window=[])

    assert result is None
    mock_compact.assert_not_called()
    assert session.session_context == [{"role": "user", "content": "hello"}]


async def test_compact_context_window_not_found_raises_value_error():
    """compact_context() raises ValueError when window is not in session_context."""
    strategy = SimpleCompaction()
    session = Session(session_config=SessionConfig(compaction_strategy=strategy))
    session.session_context = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    window = [{"role": "user", "content": "not-in-context"}]

    with patch.object(strategy, "compact", new=AsyncMock(return_value={"role": "assistant", "content": "summary"})):
        with pytest.raises(
            ValueError,
            match="Supplied window is not a contiguous subset of session_context",
        ):
            await session.compact_context(window=window)


async def test_compact_context_full_replacement_with_explicit_window():
    """compact_context(window=...) replaces the window with summary in context."""
    strategy = SimpleCompaction()
    session = Session(session_config=SessionConfig(compaction_strategy=strategy))
    session.session_context = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "bye"},
    ]
    window = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    with patch.object(strategy, "compact", new=AsyncMock(return_value={"role": "assistant", "content": "greeting summary"})):
        result = await session.compact_context(window=window)

    assert result["content"] == "greeting summary"
    assert len(session.session_context) == 2
    assert session.session_context[0].content == "greeting summary"
    assert session.session_context[1]["content"] == "bye"
