"""Tests for sync service module."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tinycua_backend.sync.service import SyncService


@pytest.fixture
def mock_session_store():
    """Create a mock SessionStore."""
    store = MagicMock()
    mock_session = MagicMock()
    mock_session.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    mock_session.name = "Test Session"
    mock_session.user_id = "user-123"
    mock_session.created_at = datetime.now(timezone.utc)
    mock_session.updated_at = datetime.now(timezone.utc)

    store.create_session.return_value = mock_session
    store.get_session.return_value = mock_session
    store.list_sessions.return_value = [mock_session]

    mock_message = MagicMock()
    mock_message.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    mock_message.role = "user"
    mock_message.content = "Hello"
    mock_message.reasoning = None
    mock_message.turn_index = 0
    mock_message.created_at = datetime.now(timezone.utc)
    store.add_message.return_value = mock_message
    store.get_messages.return_value = [mock_message]

    return store


class TestSyncService:
    """Tests for SyncService class."""

    def test_sync_sessions_preserves_client_session_id(self, mock_session_store):
        """Test that sync_sessions preserves client session ID."""
        client_session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        mock_session_store.get_session.return_value = None

        service = SyncService()
        service._get_store = lambda: mock_session_store

        service.sync_sessions(
            user_id="user-123",
            sessions=[
                {
                    "id": client_session_id,
                    "name": "My Session",
                    "updated_at": "2026-04-26T10:00:00Z",
                }
            ],
        )

        mock_session_store.create_session.assert_called_once()
        call_kwargs = mock_session_store.create_session.call_args.kwargs
        assert call_kwargs["session_id"] == uuid.UUID(client_session_id)

    def test_sync_sessions_returns_synced(self, mock_session_store):
        """Test sync_sessions returns properly formatted result."""
        service = SyncService()
        service._get_store = lambda: mock_session_store

        result = service.sync_sessions(
            user_id="user-123",
            sessions=[
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "name": "My Session",
                    "updated_at": "2026-04-26T10:00:00Z",
                }
            ],
        )

        assert "synced" in result
        assert "conflicts" in result
        assert "errors" in result

    def test_sync_memory_persists_to_database(self, mock_session_store):
        """Test that sync_memory persists memories to database."""
        service = SyncService()
        service._get_store = lambda: mock_session_store

        result = service.sync_memory(
            user_id="user-123",
            memories=[
                {
                    "session_id": "11111111-1111-1111-1111-111111111111",
                    "role": "user",
                    "content": "Hello",
                }
            ],
        )

        mock_session_store.add_message.assert_called_once()
        assert result["synced"]

    def test_pull_updates_returns_sessions_and_memories(self, mock_session_store):
        """Test pull_updates returns both sessions and memories."""
        service = SyncService()
        service._get_store = lambda: mock_session_store

        result = service.pull_updates(user_id="user-123")

        assert "sessions" in result
        assert "memories" in result
        assert len(result["sessions"]) > 0
        assert len(result["memories"]) > 0
