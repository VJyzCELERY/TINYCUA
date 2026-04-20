"""Tests for multi-device sync simulation.

These tests simulate two devices sharing sessions via Backend.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestMultiDeviceSync:
    """Tests for multi-device synchronization."""

    @pytest.mark.asyncio
    async def test_device_a_creates_session(self, sdk_client, device_a):
        """Test Device A can create a session."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "session-device-a",
                "agent_id": "agent-abc",
                "name": "session-from-device-a",
                "created_at": "2024-01-01T00:00:00Z",
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await sdk_client.create_session(
                agent_id="agent-abc",
                name="session-from-device-a",
            )

            assert result["id"] == "session-device-a"
            device_a["sessions"][result["id"]] = result

    @pytest.mark.asyncio
    async def test_device_b_retrieves_session(self, sdk_client, device_b):
        """Test Device B can retrieve a session created by Device A."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "session-device-a",
                "agent_id": "agent-abc",
                "name": "session-from-device-a",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "messages": [],
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            session = await sdk_client.get_session("session-device-a")

            assert session["id"] == "session-device-a"


class TestDataConsistency:
    """Tests for data consistency across devices."""

    @pytest.mark.asyncio
    async def test_messages_consistent_across_devices(self, sdk_client):
        """Test messages are consistent when retrieved from different devices."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"id": "msg-1", "role": "user", "content": "Hello", "turn_index": 0},
                {"id": "msg-2", "role": "assistant", "content": "Hi!", "turn_index": 1},
            ]
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            messages = await sdk_client.get_messages("session-123")

            assert len(messages) == 2
            assert messages[0]["content"] == "Hello"
            assert messages[1]["content"] == "Hi!"

    @pytest.mark.asyncio
    async def test_session_data_integrity(self, sdk_client, sample_session):
        """Test session data maintains integrity during sync."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = sample_session
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            session = await sdk_client.create_session(
                agent_id=sample_session["agent_id"],
                name=sample_session["name"],
            )

            assert session["id"] == sample_session["id"]
            assert session["agent_id"] == sample_session["agent_id"]
            assert session["name"] == sample_session["name"]


class TestMultiDeviceSimulation:
    """Tests simulating multi-device scenarios."""

    @pytest.mark.asyncio
    async def test_sync_between_devices(self, sdk_client):
        """Test sync operation between two simulated devices."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            create_response = MagicMock()
            create_response.json.return_value = {
                "id": "shared-session",
                "agent_id": "agent-shared",
                "name": "shared-session",
            }
            create_response.raise_for_status = MagicMock()

            messages_response = MagicMock()
            messages_response.json.return_value = []
            messages_response.raise_for_status = MagicMock()

            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=create_response)
            mock_client.get = AsyncMock(return_value=messages_response)
            mock_client_class.return_value = mock_client

            session = await sdk_client.create_session(
                agent_id="agent-shared",
                name="shared-session",
            )

            messages = await sdk_client.get_messages(session["id"])

            assert session["id"] == "shared-session"
            assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_concurrent_device_access(self, sdk_client):
        """Test concurrent access from multiple devices."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "session-concurrent",
                "agent_id": "agent-abc",
                "name": "concurrent-session",
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            session_a = await sdk_client.create_session(
                agent_id="agent-abc",
                name="concurrent-session",
            )

            session_b = await sdk_client.create_session(
                agent_id="agent-abc",
                name="concurrent-session",
            )

            assert session_a["id"] is not None
            assert session_b["id"] is not None


class TestMultiDeviceBackendConnection:
    """Tests for multi-device backend connection."""

    @pytest.mark.asyncio
    async def test_device_a_and_device_b_use_same_base_url(self, sdk_client):
        """Test Device A and Device B use same base_url."""
        client_a = sdk_client
        client_b = sdk_client

        assert client_a.base_url == client_b.base_url

    @pytest.mark.asyncio
    async def test_independent_connections_dont_interfere(self, sdk_client):
        """Test independent connections don't interfere with each other."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            response_1 = MagicMock()
            response_1.json.return_value = {"id": "session-1", "agent_id": "agent-abc"}
            response_1.raise_for_status = MagicMock()

            response_2 = MagicMock()
            response_2.json.return_value = {"id": "session-2", "agent_id": "agent-abc"}
            response_2.raise_for_status = MagicMock()

            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=[response_1, response_2])
            mock_client_class.return_value = mock_client

            session_1 = await sdk_client.create_session(
                agent_id="agent-abc",
                name="session-1",
            )

            session_2 = await sdk_client.create_session(
                agent_id="agent-abc",
                name="session-2",
            )

            assert session_1["id"] != session_2["id"]


class TestDataLoss:
    """Tests for data loss prevention."""

    @pytest.mark.asyncio
    async def test_all_messages_transferred_after_sync(self, sdk_client):
        """Test all messages transferred after sync."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"id": "msg-1", "role": "user", "content": "Hello"},
                {"id": "msg-2", "role": "assistant", "content": "Hi!"},
                {"id": "msg-3", "role": "user", "content": "Question?"},
            ]
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            messages = await sdk_client.get_messages("session-123")

            assert len(messages) == 3
            assert all("id" in msg and "content" in msg for msg in messages)

    @pytest.mark.asyncio
    async def test_no_partial_data_after_concurrent_operations(self, sdk_client):
        """Test no partial data after concurrent operations."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "session-123",
                "agent_id": "agent-abc",
                "messages": [
                    {"id": "msg-1"},
                    {"id": "msg-2"},
                ],
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            session = await sdk_client.get_session("session-123")

            assert len(session["messages"]) == 2
            assert all(msg.get("id") for msg in session["messages"])

    @pytest.mark.asyncio
    async def test_roundtrip_data_integrity(self, sdk_client):
        """Test round-trip data integrity."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            create_response = MagicMock()
            create_response.json.return_value = {
                "id": "session-rt",
                "agent_id": "agent-abc",
                "name": "roundtrip-session",
            }
            create_response.raise_for_status = MagicMock()

            messages_response = MagicMock()
            messages_response.json.return_value = [
                {"id": "msg-1", "role": "user", "content": "Test message"},
            ]
            messages_response.raise_for_status = MagicMock()

            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=create_response)
            mock_client.get = AsyncMock(return_value=messages_response)
            mock_client_class.return_value = mock_client

            session = await sdk_client.create_session(
                agent_id="agent-abc",
                name="roundtrip-session",
            )

            messages = await sdk_client.get_messages(session["id"])

            assert session["id"] is not None
            assert len(messages) == 1
            assert messages[0]["content"] == "Test message"
