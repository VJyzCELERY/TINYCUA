"""Integration tests for local storage with agent context tools."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tinycua_sdk.agent import Agent
from tinycua_sdk.storage import SessionStore
from tinycua_sdk.tools.context_tools import (
    get_context_summary_tool,
    get_recent_turns_tool,
    search_context_grep_tool,
)


class TestLocalStorageWithAgent:
    """Integration tests for storage + agent context tools."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()
        return store

    @pytest.fixture
    def session_with_messages(self, temp_db):
        """Create session with test messages."""
        session = temp_db.create_session(name="Test Session", user_id="user-1")

        messages = [
            ("user", "Hello, my name is Bob"),
            ("assistant", "Hi Bob! Nice to meet you."),
            ("user", "What's the weather like today?"),
            ("assistant", "The weather today is sunny, 72°F."),
            ("user", "Remember my favorite color is blue"),
            ("assistant", "I'll remember that your favorite color is blue!"),
        ]

        for role, content in messages:
            temp_db.add_message(session.id, role, content)

        temp_db.update_full_context(session.id)

        summary_text = """# Conversation Summary
- User introduced themselves as Bob
- User asked about weather (sunny, 72°F)
- User shared that their favorite color is blue"""
        temp_db.update_summary(session.id, summary_text)

        return session, temp_db

    def test_grep_tool_finds_name(self, session_with_messages):
        """Test grep tool can find user's name."""
        session, store = session_with_messages

        grep_tool = search_context_grep_tool(store, session.id)
        result = grep_tool.invoke(query="Bob")

        assert "results" in result
        assert len(result["results"]) > 0
        assert "Bob" in result["results"][0]["content"]

    def test_grep_tool_finds_color(self, session_with_messages):
        """Test grep tool can find favorite color."""
        session, store = session_with_messages

        grep_tool = search_context_grep_tool(store, session.id)
        result = grep_tool.invoke(query="blue")

        assert "results" in result
        assert len(result["results"]) > 0
        assert "blue" in result["results"][0]["content"]

    def test_recent_turns_returns_messages(self, session_with_messages):
        """Test recent turns returns the most recent messages."""
        session, store = session_with_messages

        recent_tool = get_recent_turns_tool(store, session.id)
        result = recent_tool.invoke(count=3)

        assert "turns" in result
        assert len(result["turns"]) == 3

    def test_summary_tool_returns_summary(self, session_with_messages):
        """Test summary tool returns session summary."""
        session, store = session_with_messages

        summary_tool = get_context_summary_tool(store, session.id)
        result = summary_tool.invoke()

        assert result["has_summary"] is True
        assert result["summary"] is not None
        assert "Bob" in result["summary"]

    def test_context_tools_without_session_id_returns_error(self, temp_db):
        """Test context tools return error when no session ID provided."""
        grep_tool = search_context_grep_tool(temp_db, None)
        result = grep_tool.invoke(query="test")

        assert "error" in result
        assert "No active session" in result["error"]

    def test_full_storage_flow(self, temp_db):
        """Test complete storage flow: create, add, search, retrieve."""
        session = temp_db.create_session(name="Flow Test")

        temp_db.add_message(session.id, "user", "My email is bob@example.com")
        temp_db.add_message(session.id, "assistant", "I'll remember that.")

        temp_db.update_full_context(session.id)

        results = temp_db.search_grep(session.id, "email")
        assert len(results) > 0
        assert "bob@example.com" in results[0]["content"]

        recent = temp_db.get_recent_turns(session.id, count=2)
        assert len(recent) == 2

        summary = temp_db.get_summary(session.id)
        assert summary is None

        temp_db.update_summary(session.id, "# Summary\nUser shared email")
        summary = temp_db.get_summary(session.id)
        assert summary is not None
        assert "email" in summary

    def test_message_reasoning_field(self, temp_db):
        """Test message stores reasoning field."""
        session = temp_db.create_session(name="Reasoning Test")

        msg = temp_db.add_message(
            session.id,
            "assistant",
            "Let me think about this...",
            reasoning="Thinking about user's question",
        )

        assert msg.reasoning == "Thinking about user's question"

    def test_session_list_filtering(self, temp_db):
        """Test listing sessions with user filter."""
        temp_db.create_session(name="Session 1", user_id="user-1")
        temp_db.create_session(name="Session 2", user_id="user-1")
        temp_db.create_session(name="Session 3", user_id="user-2")

        user1_sessions = temp_db.list_sessions(user_id="user-1")
        assert len(user1_sessions) == 2

        user2_sessions = temp_db.list_sessions(user_id="user-2")
        assert len(user2_sessions) == 1

        all_sessions = temp_db.list_sessions()
        assert len(all_sessions) == 3

    def test_archive_and_exclude_from_recent(self, temp_db):
        """Test archived messages excluded from recent turns."""
        session = temp_db.create_session(name="Archive Test")

        msg1 = temp_db.add_message(session.id, "user", "Message 1")
        msg2 = temp_db.add_message(session.id, "user", "Message 2")

        temp_db.archive_message(msg1.id)

        recent = temp_db.get_recent_turns(session.id, count=5)
        recent_contents = [t.content for t in recent]

        assert "Message 1" not in recent_contents
        assert "Message 2" in recent_contents
