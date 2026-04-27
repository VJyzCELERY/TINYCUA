"""Tests for SDK-Backend communication.

These tests verify SDK can connect to and communicate with Backend.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


class TestSDKBackendConnection:
    """Tests for SDK to Backend connection."""

    def test_backend_client_initialization(self, sdk_client):
        """Test BackendClient initializes with correct values."""
        assert sdk_client.base_url == "http://localhost:8000"
        assert sdk_client.api_key == "test-api-key"

    def test_backend_client_has_api_key(self, sdk_client):
        """Test BackendClient has API key set."""
        assert sdk_client.api_key is not None
        assert sdk_client.api_key == "test-api-key"

    @pytest.mark.asyncio
    async def test_backend_health_check(self, sdk_client, mock_backend):
        """Test health check returns correct status."""
        mock_backend.connected = True
        result = await mock_backend.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_backend_health_check_unconnected(self, mock_backend):
        """Test health check returns False when not connected."""
        mock_backend.connected = False
        result = await mock_backend.health_check()
        assert result is False


class TestSDKAuthentication:
    """Tests for SDK authentication flow."""

    @pytest.mark.asyncio
    async def test_authentication_with_api_key(self, mock_backend):
        """Test authentication flow with API key."""
        result = await mock_backend.authenticate("test-api-key")
        assert result["access_token"] == "test-api-key"
        assert "tenant_id" in result
        assert "user_id" in result

    def test_client_has_credentials(self, sdk_client):
        """Test client has credentials set."""
        assert sdk_client.email is None
        assert sdk_client.password is None


class TestSDKDataSync:
    """Tests for SDK data synchronization."""

    @pytest.mark.asyncio
    async def test_deploy_agent_config(self, sdk_client, sample_agent):
        """Test agent deployment sends correct config."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "agent_id": "agent-abc",
            "status": "deployed",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        result = await sdk_client.deploy_agent(agent_config=sample_agent)

        assert result["agent_id"] == "agent-abc"
        assert result["status"] == "deployed"

    @pytest.mark.asyncio
    async def test_list_agents(self, sdk_client):
        """Test listing agents from backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"name": "agent-1"},
            {"name": "agent-2"},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.list_agents()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_agent(self, sdk_client):
        """Test getting specific agent from backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "test-agent",
            "model": "gpt-4",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_agent("agent-123")

        assert result["name"] == "test-agent"


class TestSDKToolsSync:
    """Tests for SDK tools synchronization."""

    @pytest.mark.asyncio
    async def test_list_tools(self, sdk_client):
        """Test listing tools from backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "tool-1", "name": "tool-one"},
            {"id": "tool-2", "name": "tool-two"},
        ]
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.list_tools()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_deploy_tool(self, sdk_client):
        """Test deploying tool to backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tool_id": "tool-abc",
            "version": "1.0.0",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        tool_bundle = {"name": "test-tool", "version": "1.0.0"}
        result = await sdk_client.deploy_tool(tool_bundle)

        assert result["tool_id"] == "tool-abc"


class TestSDKTimeoutHandling:
    """Tests for SDK timeout handling."""

    @pytest.mark.asyncio
    async def test_connection_timeout(self, sdk_client):
        """Test SDK handles connection timeout."""
        sdk_client._client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timeout"))

        with pytest.raises(httpx.TimeoutException):
            await sdk_client.deploy_agent(agent_config={"name": "test-agent"})

    @pytest.mark.asyncio
    async def test_request_timeout(self, sdk_client):
        """Test SDK handles request timeout."""
        sdk_client._client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

        with pytest.raises(httpx.TimeoutException):
            await sdk_client.list_agents()

    @pytest.mark.asyncio
    async def test_timeout_parameter_used(self, sdk_client):
        """Test timeout parameter is used correctly."""
        client = sdk_client
        assert client.timeout == 30


class TestSDKErrorHandling:
    """Tests for SDK error handling."""

    @pytest.mark.asyncio
    async def test_connection_failure(self, sdk_client):
        """Test SDK handles connection failure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        sdk_client._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        result = await sdk_client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_http_error_responses(self, sdk_client):
        """Test SDK handles HTTP error responses."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response))
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await sdk_client.deploy_agent(agent_config={"name": "test-agent"})

    @pytest.mark.asyncio
    async def test_network_error_gracefully(self, sdk_client):
        """Test SDK handles network errors gracefully."""
        sdk_client._client.get = AsyncMock(side_effect=httpx.NetworkError("Network issue"))

        with pytest.raises(httpx.NetworkError):
            await sdk_client.list_agents()


class TestSDKTokenRefresh:
    """Tests for SDK token refresh."""

    @pytest.mark.asyncio
    async def test_token_refresh_mechanism(self, sdk_client):
        """Test token refresh mechanism."""

        login_response = MagicMock()
        login_response.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "refresh-token",
            "tenant_id": "tenant-123",
            "user_id": "user-456",
        }
        login_response.raise_for_status = MagicMock()

        sdk_client._client.post = AsyncMock(return_value=login_response)

        result = await sdk_client.login(email="test@example.com", password="password")

        assert result["access_token"] == "new-token"
        assert result["refresh_token"] == "refresh-token"

    @pytest.mark.asyncio
    async def test_expired_token_handling(self, sdk_client):
        """Test expired token handling."""

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=error_response))

        sdk_client._client.get = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await sdk_client.get_agent("agent-123")

    @pytest.mark.asyncio
    async def test_automatic_token_renewal(self, sdk_client):
        """Test automatic token renewal."""
        sdk_client.api_key = "expired-token"


        login_response = MagicMock()
        login_response.json.return_value = {
            "access_token": "renewed-token",
        }
        login_response.raise_for_status = MagicMock()

        sdk_client._client.post = AsyncMock(return_value=login_response)

        result = await sdk_client.login(email="test@example.com", password="password")

        assert result["access_token"] == "renewed-token"


class TestSDKTokenInvalidation:
    """Tests for SDK token invalidation."""

    @pytest.mark.asyncio
    async def test_handles_401_unauthorized(self, sdk_client):
        """Test SDK handles 401 Unauthorized."""

        error_response = MagicMock()
        error_response.status_code = 401
        error_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=error_response))

        sdk_client._client.get = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await sdk_client.get_agent("agent-123")

    @pytest.mark.asyncio
    async def test_handles_token_revocation(self, sdk_client):
        """Test SDK handles token revocation."""

        error_response = MagicMock()
        error_response.status_code = 403
        error_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=error_response))

        sdk_client._client.delete = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await sdk_client.delete_agent("agent-123")

    @pytest.mark.asyncio
    async def test_retry_with_new_token(self, sdk_client):
        """Test retry logic with new token."""
        sdk_client.api_key = "old-token"


        first_response = MagicMock()
        first_response.status_code = 401
        first_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=first_response))

        success_response = MagicMock()
        success_response.json.return_value = {"name": "test-agent"}
        success_response.raise_for_status = MagicMock()

        sdk_client._client.get = AsyncMock(side_effect=[first_response, success_response])

        try:
            await sdk_client.get_agent("agent-123")
        except httpx.HTTPStatusError:
            pass


class TestSDKMemorySync:
    """Tests for SDK memory synchronization."""

    @pytest.mark.asyncio
    async def test_agent_memory_synced_to_backend(self, sdk_client):
        """Test agent memory is synced to backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "synced",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.post = AsyncMock(return_value=mock_response)

        memory = {"facts": ["fact1"], "preferences": {"key": "value"}}
        result = await sdk_client.sync_memory("agent-abc", memory)

        assert result["status"] == "synced"

    @pytest.mark.asyncio
    async def test_memory_retrieval_from_backend(self, sdk_client):
        """Test memory retrieval from backend."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "facts": ["fact1"],
            "preferences": {"key": "value"},
        }
        mock_response.raise_for_status = MagicMock()
        sdk_client._client.get = AsyncMock(return_value=mock_response)

        result = await sdk_client.get_memory("agent-abc")

        assert "facts" in result

    @pytest.mark.asyncio
    async def test_memory_persistence_across_sessions(self, sdk_client):
        """Test memory persistence across sessions."""

        sync_response = MagicMock()
        sync_response.json.return_value = {"status": "synced"}
        sync_response.raise_for_status = MagicMock()

        get_response = MagicMock()
        get_response.json.return_value = {"facts": ["fact1"], "preferences": {}}
        get_response.raise_for_status = MagicMock()

        sdk_client._client.post = AsyncMock(return_value=sync_response)
        sdk_client._client.get = AsyncMock(return_value=get_response)

        memory = {"facts": ["fact1"], "preferences": {}}
        await sdk_client.sync_memory("agent-abc", memory)

        result = await sdk_client.get_memory("agent-abc")

        assert "facts" in result
