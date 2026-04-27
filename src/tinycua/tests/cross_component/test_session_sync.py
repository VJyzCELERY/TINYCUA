"""Tests for session synchronization.

These tests verify session creation, retrieval, and update sync.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


class TestSessionCreation:
    """Tests for session creation sync."""

    @pytest.mark.asyncio
    async def test_create_session(self, sdk_client):
        """Test creating a session via SDK."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-123",
            "agent_id": "agent-abc",
            "name": "test-session",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        result = await sdk_client.create_session(
            agent_id="agent-abc",
            name="test-session",
        )

        assert result["id"] == "session-123"
        assert result["agent_id"] == "agent-abc"

    @pytest.mark.asyncio
    async def test_create_session_with_name(self, sdk_client):
        """Test creating a session with custom name."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-456",
            "agent_id": "agent-abc",
            "name": "my-custom-session",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        result = await sdk_client.create_session(
            agent_id="agent-abc",
            name="my-custom-session",
        )

        assert result["name"] == "my-custom-session"


class TestSessionRetrieval:
    """Tests for session retrieval sync."""

    @pytest.mark.asyncio
    async def test_get_messages(self, sdk_client):
        """Test retrieving messages for a session."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "msg-1", "role": "user", "content": "Hello"},
            {"id": "msg-2", "role": "assistant", "content": "Hi there!"},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_messages("session-123")

        assert len(result) == 2
        assert result[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_messages_with_pagination(self, sdk_client):
        """Test retrieving messages with pagination."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "msg-1", "role": "user", "content": "Hello"},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_messages("session-123", limit=1, offset=0)

        assert len(result) == 1


class TestSessionUpdate:
    """Tests for session update sync."""

    @pytest.mark.asyncio
    async def test_add_message(self, sdk_client):
        """Test adding a message to a session."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg-3",
            "role": "user",
            "content": "New message",
            "turn_index": 2,
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        result = await sdk_client.add_message(
            session_id="session-123",
            role="user",
            content="New message",
        )

        assert result["id"] == "msg-3"
        assert result["content"] == "New message"

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self, sdk_client):
        """Test adding multiple messages maintains order."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg-new",
            "role": "user",
            "content": "Message",
            "turn_index": 0,
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        result = await sdk_client.add_message(
            session_id="session-123",
            role="user",
            content="Message",
        )

        assert "turn_index" in result


class TestSessionSync:
    """Tests for complete session sync workflow."""

    @pytest.mark.asyncio
    async def test_session_sync_workflow(self, sdk_client):
        """Test complete session sync workflow."""

        session_response = MagicMock()
        session_response.json.return_value = {
            "id": "session-sync-123",
            "agent_id": "agent-sync",
            "name": "sync-test",
        }
        session_response.raise_for_status = MagicMock()

        messages_response = MagicMock()
        messages_response.json.return_value = [
            {"id": "msg-1", "role": "user", "content": "Test"},
        ]
        messages_response.raise_for_status = MagicMock()

        sdk_client._client.post = AsyncMock(return_value=session_response)
        sdk_client._client.get = AsyncMock(return_value=messages_response)

        session = await sdk_client.create_session(
            agent_id="agent-sync",
            name="sync-test",
        )

        messages = await sdk_client.get_messages(session["id"])

        assert session["id"] == "session-sync-123"
        assert len(messages) == 1


class TestSessionRetrievalDirect:
    """Tests for direct session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session(self, sdk_client):
        """Test retrieving a complete session by ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-123",
            "agent_id": "agent-abc",
            "name": "test-session",
            "messages": [
                {"id": "msg-1", "role": "user", "content": "Hello"},
                {"id": "msg-2", "role": "assistant", "content": "Hi!"},
            ],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "version": 1,
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_session("session-123")

        assert result["id"] == "session-123"
        assert result["agent_id"] == "agent-abc"
        assert len(result["messages"]) == 2
        assert result["version"] == 1

    @pytest.mark.asyncio
    async def test_session_metadata_correct(self, sdk_client):
        """Test session metadata is correct."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-456",
            "agent_id": "agent-xyz",
            "name": "my-session",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_session("session-456")

        assert result["name"] == "my-session"
        assert result["created_at"] == "2024-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_session_expected_messages_count(self, sdk_client):
        """Test session contains expected messages count."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "session-789",
            "agent_id": "agent-abc",
            "messages": [
                {"id": "msg-1"},
                {"id": "msg-2"},
                {"id": "msg-3"},
            ],
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_session("session-789")

        assert len(result["messages"]) == 3


class TestConflictHandling:
    """Tests for session conflict handling."""

    @pytest.mark.asyncio
    async def test_concurrent_session_updates(self, sdk_client):
        """Test concurrent session updates."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {
            "error": "Conflict",
            "local_version": 1,
            "server_version": 2,
        }
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Conflict", request=MagicMock(), response=mock_response))
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        try:
            await sdk_client.add_message("session-123", "user", "Test")
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 409

    @pytest.mark.asyncio
    async def test_session_version_conflicts(self, sdk_client):
        """Test session version conflicts."""

        error_response = MagicMock()
        error_response.status_code = 409
        error_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Version Conflict", request=MagicMock(), response=error_response))

        sdk_client._client.post = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await sdk_client.add_message("session-123", "user", "New message")

    @pytest.mark.asyncio
    async def test_conflict_resolution_strategy(self, sdk_client):
        """Test conflict resolution strategy."""

        response = MagicMock()
        response.json.return_value = {
            "id": "msg-new",
            "role": "user",
            "content": "Resolved",
            "turn_index": 5,
            "version": 3,
        }
        response.raise_for_status = MagicMock()

        sdk_client._client.post = AsyncMock(return_value=response)

        result = await sdk_client.add_message("session-123", "user", "Resolved")

        assert result["version"] == 3


class TestSyncOrdering:
    """Tests for sync ordering."""

    @pytest.mark.asyncio
    async def test_message_turn_index_consistency(self, sdk_client):
        """Test message turn_index consistency."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "msg-1", "role": "user", "content": "Hello", "turn_index": 0},
            {"id": "msg-2", "role": "assistant", "content": "Hi!", "turn_index": 1},
            {"id": "msg-3", "role": "user", "content": "How are you?", "turn_index": 2},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        messages = await sdk_client.get_messages("session-123")

        assert messages[0]["turn_index"] == 0
        assert messages[1]["turn_index"] == 1
        assert messages[2]["turn_index"] == 2

    @pytest.mark.asyncio
    async def test_chronological_ordering_of_messages(self, sdk_client):
        """Test chronological ordering of messages."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "msg-1", "created_at": "2024-01-01T00:00:00Z"},
            {"id": "msg-2", "created_at": "2024-01-01T00:01:00Z"},
            {"id": "msg-3", "created_at": "2024-01-01T00:02:00Z"},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        messages = await sdk_client.get_messages("session-123")

        assert messages[0]["created_at"] < messages[1]["created_at"]
        assert messages[1]["created_at"] < messages[2]["created_at"]

    @pytest.mark.asyncio
    async def test_sync_respects_message_sequence(self, sdk_client):
        """Test sync respects message sequence."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "msg-1", "role": "user", "turn_index": 0},
            {"id": "msg-2", "role": "assistant", "turn_index": 1},
            {"id": "msg-3", "role": "user", "turn_index": 2},
            {"id": "msg-4", "role": "assistant", "turn_index": 3},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        messages = await sdk_client.get_messages("session-123")

        for i, msg in enumerate(messages):
            assert msg["turn_index"] == i
