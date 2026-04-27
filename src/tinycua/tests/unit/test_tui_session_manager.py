"""Tests for TUI session manager."""

import uuid

import pytest


class TestTuiSessionManager:
    """Test TuiSessionManager class."""

    def test_session_manager_initializes(self):
        """Test session manager initializes."""
        from tinycua.tui.session_manager import TuiSessionManager

        manager = TuiSessionManager(store=None)
        assert manager._current_session_id is None
        assert manager._sessions == []

    def test_session_manager_create_session(self):
        """Test creating a new session."""
        from unittest.mock import MagicMock
        from tinycua.tui.session_manager import TuiSessionManager

        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.name = "Test Session"
        mock_store.create_session.return_value = mock_session

        manager = TuiSessionManager(store=mock_store)
        session = manager.create_session("Test Session")
        
        assert session is not None
        mock_store.create_session.assert_called_once_with("Test Session")

    def test_session_manager_list_sessions(self):
        """Test listing sessions."""
        from unittest.mock import MagicMock
        from tinycua.tui.session_manager import TuiSessionManager

        mock_store = MagicMock()
        mock_sessions = [MagicMock(), MagicMock()]
        mock_store.list_sessions.return_value = mock_sessions

        manager = TuiSessionManager(store=mock_store)
        sessions = manager.list_sessions()
        
        assert len(sessions) == 2
        mock_store.list_sessions.assert_called_once()

    def test_session_manager_delete_session(self):
        """Test deleting a session."""
        from unittest.mock import MagicMock
        from tinycua.tui.session_manager import TuiSessionManager

        mock_store = MagicMock()
        mock_store.delete_session.return_value = True

        manager = TuiSessionManager(store=mock_store)
        session_id = uuid.uuid4()
        result = manager.delete_session(session_id)
        
        assert result is True
        mock_store.delete_session.assert_called_once_with(session_id)

    def test_session_manager_set_current_session(self):
        """Test setting current session."""
        from unittest.mock import MagicMock
        from tinycua.tui.session_manager import TuiSessionManager

        mock_store = MagicMock()
        manager = TuiSessionManager(store=mock_store)
        
        session_id = uuid.uuid4()
        manager.set_current_session(session_id)
        
        assert manager._current_session_id == session_id

    def test_session_manager_get_current_session(self):
        """Test getting current session."""
        from unittest.mock import MagicMock
        from tinycua.tui.session_manager import TuiSessionManager

        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        
        manager = TuiSessionManager(store=mock_store)
        manager._current_session_id = mock_session.id
        
        mock_store.get_session.return_value = mock_session
        session = manager.get_current_session()
        
        assert session == mock_session

    def test_session_manager_resume_session(self):
        """Test resuming a session."""
        from unittest.mock import MagicMock
        from tinycua.tui.session_manager import TuiSessionManager

        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_store.get_session.return_value = mock_session

        manager = TuiSessionManager(store=mock_store)
        session = manager.resume_session(mock_session.id)
        
        assert manager._current_session_id == mock_session.id
        assert session == mock_session
