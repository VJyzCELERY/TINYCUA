"""Tests for BackendClient in tinycua package."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBackendClient:
    """Test BackendClient methods."""

    def test_client_initialization(self):
        """Test client initializes with correct values."""
        from tinycua.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
        )
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "test-key"

    def test_client_with_custom_headers(self):
        """Test client accepts custom headers."""
        from tinycua.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
            headers={"X-Custom-Auth": "token123"},
        )
        assert client.headers == {"X-Custom-Auth": "token123"}

    def test_get_headers_with_api_key(self):
        """Test _get_headers includes auth header."""
        from tinycua.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
        )
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_deploy_agent(self):
        """Test deploy_agent sends correct request."""
        from tinycua.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "agent_id": "agent-abc-123",
                "status": "deployed",
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = BackendClient(
                base_url="http://localhost:8000",
                api_key="test-key",
            )

            result = await client.deploy_agent(
                agent_config={"name": "test-agent"},
            )

            assert result["agent_id"] == "agent-abc-123"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent(self):
        """Test get_agent sends correct request."""
        from tinycua.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "name": "test-agent",
                "model": "gpt-4",
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = BackendClient(
                base_url="http://localhost:8000",
                api_key="test-key",
            )

            result = await client.get_agent("agent-123")

            assert result["name"] == "test-agent"
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_agent(self):
        """Test delete_agent sends correct request."""
        from tinycua.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = BackendClient(
                base_url="http://localhost:8000",
                api_key="test-key",
            )

            await client.delete_agent("agent-123")

            mock_client.delete.assert_called_once()
            call_args = mock_client.delete.call_args
            assert "agent-123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_agents(self):
        """Test list_agents returns list of agents."""
        from tinycua.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"name": "agent-1"},
                {"name": "agent-2"},
            ]
            mock_response.raise_for_status = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = BackendClient(
                base_url="http://localhost:8000",
                api_key="test-key",
            )

            result = await client.list_agents()

            assert len(result) == 2
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health_check returns True for healthy backend."""
        from tinycua.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = BackendClient(base_url="http://localhost:8000")

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test health_check returns False for unhealthy backend."""
        from tinycua.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client_class.return_value = mock_client

            client = BackendClient(base_url="http://localhost:8000")

            result = await client.health_check()

            assert result is False
