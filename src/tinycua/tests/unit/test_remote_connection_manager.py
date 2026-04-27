"""Tests for RemoteConnectionManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRemoteConnectionManager:
    """Test RemoteConnectionManager methods."""

    def test_manager_initialization(self):
        """Test manager initializes with correct values."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(
            backend_url="http://localhost:8000",
        )
        assert manager.backend_url == "http://localhost:8000"
        assert manager._connected is False
        assert manager._mode == "local"

    def test_manager_with_config(self):
        """Test manager accepts config object."""
        from tinycua.remote import RemoteConnectionManager, RemoteConfig

        config = RemoteConfig(
            backend_url="http://remote.example.com",
            email="user@example.com",
            api_key="secret-key",
        )
        manager = RemoteConnectionManager(config=config)
        assert manager.backend_url == "http://remote.example.com"
        assert manager.config.email == "user@example.com"

    def test_default_mode_is_local(self):
        """Test default mode is local."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager()
        assert manager.mode == "local"
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test connect establishes connection."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(
            backend_url="http://localhost:8000",
            api_key="test-key",
        )

        with patch("tinycua.clients.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client

            result = await manager.connect()

            assert result is True
            assert manager.is_connected is True
            assert manager.mode == "remote"

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connect handles failure gracefully."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(
            backend_url="http://localhost:8000",
            api_key="test-key",
        )

        with patch("tinycua.clients.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await manager.connect()

            assert result is False
            assert manager.is_connected is False
            assert manager.mode == "local"

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect closes connection."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        manager._connected = True
        manager._mode = "remote"

        await manager.disconnect()

        assert manager.is_connected is False
        assert manager.mode == "local"

    @pytest.mark.asyncio
    async def test_test_connection(self):
        """Test test_connection verifies backend and caches client."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")

        with patch("tinycua.clients.BackendClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.health_check = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client

            success, error = await manager.test_connection()

            assert success is True
            mock_client.health_check.assert_called_once()
            mock_client.close.assert_not_awaited()
            assert manager._client is mock_client

    @pytest.mark.asyncio
    async def test_test_connection_reuses_connected_client(self):
        """Test test_connection reuses existing connected client."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        existing_client = AsyncMock()
        existing_client.base_url = "http://localhost:8000"
        existing_client.health_check = AsyncMock(return_value=True)
        manager._client = existing_client
        manager._connected = True

        success, error = await manager.test_connection()

        assert success is True
        existing_client.health_check.assert_called_once()
        existing_client.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_test_connection_reuses_client_when_not_connected(self):
        """Test test_connection reuses existing client even when not connected."""
        from tinycua.remote import RemoteConnectionManager

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        existing_client = AsyncMock()
        existing_client.base_url = "http://localhost:8000"
        existing_client.health_check = AsyncMock(return_value=True)
        manager._client = existing_client
        manager._connected = False

        success, error = await manager.test_connection()

        assert success is True
        existing_client.health_check.assert_called_once()
        existing_client.close.assert_not_awaited()