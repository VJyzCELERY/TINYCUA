"""Tests for MCP client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tinycua_sdk.tools.mcp import MCPClient, MCPTool


class TestMCPClient:
    """Tests for MCPClient class."""

    def test_mcp_client_init(self):
        """MCPClient initializes with server URL."""
        client = MCPClient(server_url="http://localhost:3000")
        assert client.server_url == "http://localhost:3000"

    def test_mcp_client_init_with_headers(self):
        """MCPClient accepts custom headers."""
        headers = {"Authorization": "Bearer token"}
        client = MCPClient(server_url="http://localhost:3000", headers=headers)
        assert client.headers == headers

    @pytest.mark.asyncio
    async def test_connect_establishes_connection(self):
        """MCPClient.connect establishes connection."""
        client = MCPClient(server_url="http://localhost:3000")
        with patch("tinycua_sdk.tools.mcp.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"tools": []}
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.connect()
            assert client.connected is True

    @pytest.mark.asyncio
    async def test_fetch_tools_returns_tool_list(self):
        """MCPClient._fetch_tools returns list of tools."""
        client = MCPClient(server_url="http://localhost:3000")
        client._client = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tools": [
                {"name": "tool1", "description": "Test tool"}
            ]
        }
        client._client.request = AsyncMock(return_value=mock_response)
        
        tools = await client._fetch_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "tool1"

    def test_get_tools_returns_cached_tools(self):
        """MCPClient.get_tools returns cached tools."""
        client = MCPClient(server_url="http://localhost:3000")
        client._tools = [
            {"name": "tool1", "description": "Test tool"}
        ]
        
        tools = client.get_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "tool1"

    def test_get_tool_by_name(self):
        """MCPClient.get_tool returns tool by name."""
        client = MCPClient(server_url="http://localhost:3000")
        client._tools = [
            {"name": "tool1", "description": "Test tool"}
        ]
        
        tool = client.get_tool("tool1")
        assert tool is not None
        assert tool["name"] == "tool1"

    def test_get_tool_not_found(self):
        """MCPClient.get_tool returns None for missing tool."""
        client = MCPClient(server_url="http://localhost:3000")
        client._tools = []
        
        tool = client.get_tool("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_call_tool_invokes_tool(self):
        """MCPClient.call_tool calls tool and returns result."""
        client = MCPClient(server_url="http://localhost:3000")
        client._tools = [{"name": "tool1"}]
        client._client = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"success": True}}
        client._client.request = AsyncMock(return_value=mock_response)
        
        result = await client.call_tool("tool1", {"arg": "value"})
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_call_tool_not_found_raises(self):
        """MCPClient.call_tool raises error for missing tool."""
        client = MCPClient(server_url="http://localhost:3000")
        client._tools = []
        
        with pytest.raises(ValueError) as exc_info:
            await client.call_tool("nonexistent", {})
        assert "not found" in str(exc_info.value)
