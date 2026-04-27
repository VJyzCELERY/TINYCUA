"""Unit tests for BackendClient connection methods."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tinycua_sdk.clients.backend import BackendClient


class TestBackendClientConnection:
    """Test cases for BackendClient connection methods."""

    @pytest.fixture
    def client(self):
        """Create a BackendClient instance."""
        return BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_create_tenant(self, client):
        """Test creating a tenant."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"tenant_id": "tenant-123", "status": "active"}
            mock_response.raise_for_status = MagicMock()
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await client.create_tenant("My Tenant")
            
            assert result["tenant_id"] == "tenant-123"
            assert client.tenant_id == "tenant-123"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client):
        """Test successful connection test."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            result = await client.test_connection()
            
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client):
        """Test failed connection test."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            
            result = await client.test_connection()
            
            assert result is False

    def test_is_local_mode_no_url(self):
        """Test local mode detection with no URL."""
        client = BackendClient(base_url="")
        
        assert client.is_local_mode() is True

    def test_is_local_mode_with_url(self):
        """Test local mode detection with URL."""
        client = BackendClient(base_url="http://localhost:8000")
        
        assert client.is_local_mode() is False

    def test_is_local_mode_none(self):
        """Test local mode detection with None URL."""
        client = BackendClient(base_url="")
        
        result = client.is_local_mode()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_login_updates_credentials(self, client):
        """Test that login updates credentials."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "access_token": "new-token",
                "tenant_id": "tenant-456",
                "user_id": "user-789",
            }
            mock_response.raise_for_status = MagicMock()
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await client.login(email="test@example.com", password="password")
            
            assert client.api_key == "new-token"
            assert client.tenant_id == "tenant-456"
            assert client.user_id == "user-789"
