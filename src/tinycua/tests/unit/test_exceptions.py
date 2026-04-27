"""Tests verifying StorageError is raised from local_session_store.py methods."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from tinycua.exceptions import StorageError
from tinycua.storage.local_session_store import LocalSessionStore


class TestLocalSessionStoreExceptions:
    """Tests that LocalSessionStore raises StorageError on underlying failures."""

    @pytest.fixture
    def failing_store(self):
        """Create a mock SessionStore that always raises OSError."""
        store = MagicMock()
        store.create_session.side_effect = OSError("db locked")
        store.get_session.side_effect = OSError("db locked")
        store.get_session_by_name.side_effect = OSError("db locked")
        store.list_sessions.side_effect = OSError("db locked")
        store.update_session.side_effect = OSError("db locked")
        store.delete_session.side_effect = OSError("db locked")
        store.add_message.side_effect = OSError("db locked")
        store.get_messages.side_effect = OSError("db locked")
        store.get_recent_turns.side_effect = OSError("db locked")
        return store

    @pytest.fixture
    def local_store(self, failing_store):
        """Create a LocalSessionStore wrapping the failing store."""
        return LocalSessionStore(failing_store)

    def test_create_session_raises_storage_error(self, local_store):
        """Test create_session raises StorageError."""
        with pytest.raises(StorageError, match="Failed to create session"):
            local_store.create_session("test")

    def test_get_session_raises_storage_error(self, local_store):
        """Test get_session raises StorageError."""
        sid = uuid.uuid4()
        with pytest.raises(StorageError, match="Failed to get session"):
            local_store.get_session(sid)

    def test_get_session_by_name_raises_storage_error(self, local_store):
        """Test get_session_by_name raises StorageError."""
        with pytest.raises(StorageError, match="Failed to get session by name"):
            local_store.get_session_by_name("test")

    def test_list_sessions_raises_storage_error(self, local_store):
        """Test list_sessions raises StorageError."""
        with pytest.raises(StorageError, match="Failed to list sessions"):
            local_store.list_sessions()

    def test_update_session_raises_storage_error(self, local_store):
        """Test update_session raises StorageError."""
        sid = uuid.uuid4()
        with pytest.raises(StorageError, match="Failed to update session"):
            local_store.update_session(sid, name="new")

    def test_delete_session_raises_storage_error(self, local_store):
        """Test delete_session raises StorageError."""
        sid = uuid.uuid4()
        with pytest.raises(StorageError, match="Failed to delete session"):
            local_store.delete_session(sid)

    def test_add_message_raises_storage_error(self, local_store):
        """Test add_message raises StorageError."""
        sid = uuid.uuid4()
        with pytest.raises(StorageError, match="Failed to add message"):
            local_store.add_message(sid, "user", "hello")

    def test_get_messages_raises_storage_error(self, local_store):
        """Test get_messages raises StorageError."""
        sid = uuid.uuid4()
        with pytest.raises(StorageError, match="Failed to get messages"):
            local_store.get_messages(sid)

    def test_get_recent_turns_raises_storage_error(self, local_store):
        """Test get_recent_turns raises StorageError."""
        sid = uuid.uuid4()
        with pytest.raises(StorageError, match="Failed to get recent turns"):
            local_store.get_recent_turns(sid)
