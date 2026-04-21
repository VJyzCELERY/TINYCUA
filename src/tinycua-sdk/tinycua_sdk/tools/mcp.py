"""MCP (Model Context Protocol) client integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx


_mcp_logger = logging.getLogger("tinycua_sdk.mcp")


class MCPTool:
    """Represents a tool from an MCP server."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        """Initialize MCP tool.

        Args:
            name: Tool name.
            description: Tool description.
            input_schema: JSON schema for tool input.
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema


class MCPClient:
    """Client for connecting to MCP servers.

    Handles MCP protocol for tool discovery and invocation.
    """

    def __init__(
        self,
        server_url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize MCP client.

        Args:
            server_url: URL of the MCP server.
            headers: Optional HTTP headers.
            timeout: Request timeout in seconds.
        """
        self.server_url = server_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._tools: list[dict[str, Any]] = []
        self.connected = False

    async def connect(self) -> None:
        """Establish connection to MCP server."""
        _mcp_logger.info(f"Connecting to MCP server: {self.server_url}")
        self._client = httpx.AsyncClient(
            base_url=self.server_url,
            headers=self.headers,
            timeout=self.timeout,
        )
        await self._fetch_tools()
        self.connected = True
        _mcp_logger.info(f"Connected to MCP server with {len(self._tools)} tools")

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make request to MCP server."""
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        response = await self._client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _fetch_tools(self) -> list[dict[str, Any]]:
        """Fetch available tools from MCP server."""
        _mcp_logger.debug("Fetching tools from MCP server")
        try:
            result = await self._request("GET", "/tools")
            self._tools = result.get("tools", [])
            _mcp_logger.debug(f"Fetched {len(self._tools)} tools")
            return self._tools
        except Exception as e:
            _mcp_logger.warning(f"Failed to fetch tools: {e}")
            self._tools = []
            return self._tools

    def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools in SDK format.

        Returns:
            List of tool schemas.
        """
        return [
            {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {}),
            }
            for tool in self._tools
        ]

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """Get tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool schema or None if not found.
        """
        for tool in self._tools:
            if tool.get("name") == name:
                return {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("inputSchema", {}),
                }
        return None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Call an MCP tool.

        Args:
            name: Tool name to call.
            arguments: Tool arguments.

        Returns:
            Tool result.

        Raises:
            ValueError: If tool not found.
            RuntimeError: If not connected.
        """
        tool = self.get_tool(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found")

        _mcp_logger.info(f"Calling MCP tool: {name}")

        result = await self._request(
            "POST", f"/tools/{name}", json=arguments,
        )
        return result.get("result")

    async def close(self) -> None:
        """Close connection to MCP server."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self.connected = False
            _mcp_logger.info("Disconnected from MCP server")

    def __repr__(self) -> str:
        return f"MCPClient(server_url={self.server_url!r}, connected={self.connected})"
