"""Tests for session display - session list, session detail, message formatting."""

import pytest


class TestSessionListRendering:
    """Test session list display."""

    def test_session_list_displays(self, sample_session):
        """Test session list displays correctly."""
        try:
            from tinycua.tui.sessions import SessionList
        except ImportError:
            pytest.skip("SessionList not yet implemented")

        sessions = [sample_session]
        view = SessionList(sessions=sessions)
        output = view.render()
        assert "Test Session" in output

    def test_session_list_empty_state(self, empty_session_list):
        """Test empty session list displays correctly."""
        try:
            from tinycua.tui.sessions import SessionList
        except ImportError:
            pytest.skip("SessionList not yet implemented")

        view = SessionList(sessions=empty_session_list)
        output = view.render()
        assert "empty" in output.lower() or "no" in output.lower()

    def test_session_list_pagination(self):
        """Test session list pagination."""
        try:
            from tinycua.tui.sessions import SessionList
        except ImportError:
            pytest.skip("SessionList not yet implemented")

        sessions = [{"id": f"session-{i}", "name": f"Session {i}"} for i in range(25)]
        view = SessionList(sessions=sessions, page_size=10)
        assert view.current_page == 0
        view.next_page()
        assert view.current_page == 1
        view.next_page()
        assert view.current_page == 2


class TestSessionDetailDisplay:
    """Test session detail view."""

    def test_session_messages_display(self, sample_session):
        """Test session messages are displayed."""
        try:
            from tinycua.tui.sessions import SessionDetail
        except ImportError:
            pytest.skip("SessionDetail not yet implemented")

        detail = SessionDetail(session=sample_session)
        output = detail.render_messages()
        assert "Hello" in output
        assert "Hi there!" in output

    def test_session_metadata_display(self, sample_session):
        """Test session metadata is displayed."""
        try:
            from tinycua.tui.sessions import SessionDetail
        except ImportError:
            pytest.skip("SessionDetail not yet implemented")

        detail = SessionDetail(session=sample_session)
        output = detail.render_metadata()
        assert "Test Session" in output
        assert "test-session-001" in output

    def test_session_timestamps(self, sample_session):
        """Test session timestamps are displayed."""
        try:
            from tinycua.tui.sessions import SessionDetail
        except ImportError:
            pytest.skip("SessionDetail not yet implemented")

        detail = SessionDetail(session=sample_session)
        output = detail.render_timestamps()
        assert "2024-01-01" in output


class TestMessageFormatting:
    """Test message formatting."""

    def test_user_message_formatting(self):
        """Test user messages are formatted correctly."""
        try:
            from tinycua.tui.sessions import MessageFormatter
        except ImportError:
            pytest.skip("MessageFormatter not yet implemented")

        formatter = MessageFormatter()
        output = formatter.format_user_message("Hello world")
        assert "user" in output.lower() or "you" in output.lower()
        assert "Hello world" in output

    def test_assistant_message_formatting(self):
        """Test assistant messages are formatted correctly."""
        try:
            from tinycua.tui.sessions import MessageFormatter
        except ImportError:
            pytest.skip("MessageFormatter not yet implemented")

        formatter = MessageFormatter()
        output = formatter.format_assistant_message("Response")
        assert "assistant" in output.lower() or "ai" in output.lower()
        assert "Response" in output

    def test_tool_result_formatting(self):
        """Test tool results are formatted correctly."""
        try:
            from tinycua.tui.sessions import MessageFormatter
        except ImportError:
            pytest.skip("MessageFormatter not yet implemented")

        formatter = MessageFormatter()
        output = formatter.format_tool_result("Tool output")
        assert "tool" in output.lower() or "result" in output.lower()
        assert "Tool output" in output
