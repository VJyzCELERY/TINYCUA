"""Tests for responses client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestResponsesClient:
    def test_client_initialization(self):
        from tinycua_sdk.clients import ResponsesClient

        client = ResponsesClient(base_url="http://localhost:8000", api_key="test-key")
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "test-key"

    def test_client_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("TINYCUA_API_URL", "http://custom:9000")
        monkeypatch.setenv("TINYCUA_API_KEY", "env-key")

        from tinycua_sdk.clients import ResponsesClient

        client = ResponsesClient()
        assert client.base_url == "http://custom:9000"
        assert client.api_key == "env-key"

    def test_client_default_base_url(self):
        from tinycua_sdk.clients import ResponsesClient

        client = ResponsesClient()
        assert client.base_url == "http://localhost:1234/v1"

    def test_client_no_double_v1_appending(self):
        from tinycua_sdk.clients import ResponsesClient

        client = ResponsesClient(base_url="http://localhost:1234/v1")
        # httpx.AsyncClient appends a trailing slash to base_url;
        # the important thing is that /v1 is NOT duplicated.
        assert "/v1/v1" not in str(client._client.base_url)
        assert client.base_url == "http://localhost:1234/v1"

    @pytest.mark.asyncio
    async def test_create_request(self):
        from tinycua_sdk.clients import ResponsesClient
        from tinycua_sdk.models import ResponseRequest

        with patch("tinycua_sdk.clients.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "resp-123",
                "model": "gpt-4o-mini",
                "choices": [],
                "usage": {},
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = ResponsesClient(base_url="http://localhost:8000")
            client._client = mock_client

            request = ResponseRequest(
                model="gpt-4o-mini", input=[{"role": "user", "content": "hello"}]
            )
            response = await client.create(request)

            assert response.id == "resp-123"
            assert response.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_create_request_with_chat_completions(self):
        from tinycua_sdk.clients import ResponsesClient
        from tinycua_sdk.models import ResponseRequest

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "resp-123",
                "model": "gpt-4o-mini",
                "choices": [],
                "usage": {},
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = ResponsesClient(base_url="http://localhost:8000")
            client._client = mock_client

            request = ResponseRequest(
                model="gpt-4o-mini", input=[{"role": "user", "content": "hello"}]
            )
            response = await client.create(request)

            assert response.id == "resp-123"
            assert response.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_create_adds_trace_id(self):
        from tinycua_sdk.clients import ResponsesClient
        from tinycua_sdk.models import ResponseRequest

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "id": "resp-123",
                "model": "test",
                "choices": [],
                "usage": {},
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            client = ResponsesClient(base_url="http://localhost:8000")
            client._client = mock_client

            request = ResponseRequest(model="test", input=[])
            await client.create(request)

            call_kwargs = mock_client.post.call_args.kwargs
            assert "X-Trace-Id" in call_kwargs.get("headers", {})


class TestResponseRequest:
    def test_request_defaults(self):
        from tinycua_sdk.models import ResponseRequest

        request = ResponseRequest(model="gpt-4o-mini")
        assert request.model == "gpt-4o-mini"
        assert request.stream is False
        assert request.temperature == 1.0

    def test_request_with_tools(self):
        from tinycua_sdk.models import ResponseRequest, ToolDefinition

        tool = ToolDefinition(name="test", description="A test", parameters={})
        request = ResponseRequest(model="test", tools=[tool])
        assert len(request.tools) == 1


class TestBackendClient:
    def test_client_initialization(self):
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
        )
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "test-key"

    def test_client_with_custom_headers(self):
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
            headers={"X-Custom-Auth": "token123"},
        )
        assert client.headers == {"X-Custom-Auth": "token123"}

    def test_get_headers_with_api_key(self):
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
        )
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_custom_headers(self):
        from tinycua_sdk.clients import BackendClient

        client = BackendClient(
            base_url="http://localhost:8000",
            api_key="test-key",
            headers={"X-Custom-Auth": "token123", "X-User-ID": "user-123"},
        )
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["X-Custom-Auth"] == "token123"
        assert headers["X-User-ID"] == "user-123"

    @pytest.mark.asyncio
    async def test_deploy_agent(self):
        from tinycua_sdk.clients import BackendClient

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
            call_args = mock_client.post.call_args
            assert "/v1/agents" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_agent(self):
        from tinycua_sdk.clients import BackendClient

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
        from tinycua_sdk.clients import BackendClient

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
        from tinycua_sdk.clients import BackendClient

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
        from tinycua_sdk.clients import BackendClient

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
        from tinycua_sdk.clients import BackendClient

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=OSError("Connection error"))
            mock_client_class.return_value = mock_client

            client = BackendClient(base_url="http://localhost:8000")

            result = await client.health_check()

            assert result is False
