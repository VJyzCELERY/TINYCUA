"""Unit tests for BackendClient connection methods."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tinycua_sdk.clients.backend import BackendClient


class TestBackendClientConnection:
    """Test cases for BackendClient connection methods."""

    @pytest.fixture
    def client(self):
        """Create a BackendClient instance with mocked HTTP client."""
        with patch("httpx.AsyncClient"):
            return BackendClient(
                base_url="http://localhost:8000",
                api_key="test-key",
            )

    def _mock_response(self, json_data=None, status_code=200):
        """Helper to create a mock response."""
        mock_response = MagicMock()
        if json_data is not None:
            mock_response.json.return_value = json_data
        mock_response.status_code = status_code
        mock_response.raise_for_status = MagicMock()
        return mock_response

    @pytest.mark.asyncio
    async def test_create_tenant(self, client):
        """Test creating a tenant."""
        mock_response = self._mock_response(
            json_data={"tenant_id": "tenant-123", "status": "active"}
        )
        client._client.post = AsyncMock(return_value=mock_response)

        result = await client.create_tenant("My Tenant")

        assert result["tenant_id"] == "tenant-123"
        assert client.tenant_id == "tenant-123"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client):
        """Test successful connection test."""
        mock_response = self._mock_response(status_code=200)
        client._client.get = AsyncMock(return_value=mock_response)

        result = await client.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client):
        """Test failed connection test."""
        client._client.get = AsyncMock(side_effect=OSError("Connection failed"))

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
        mock_response = self._mock_response(
            json_data={
                "access_token": "new-token",
                "tenant_id": "tenant-456",
                "user_id": "user-789",
            }
        )
        client._client.post = AsyncMock(return_value=mock_response)

        result = await client.login(email="test@example.com", password="password")

        assert client.api_key == "new-token"
        assert client.tenant_id == "tenant-456"
        assert client.user_id == "user-789"
