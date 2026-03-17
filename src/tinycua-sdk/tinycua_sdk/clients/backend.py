"""Backend client for remote agent management."""

import httpx
from typing import Any, AsyncIterator


class BackendClient:
    """Internal client for backend communication.

    Used by Agent for deployed mode and standalone functions.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        """Initialize Backend Client.

        Args:
            base_url: Base URL of the backend server
            api_key: API key for authentication
            headers: Custom headers for auth and multi-tenancy
            timeout: Request timeout in seconds

        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = headers or {}
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with auth and custom headers.

        Returns:
            Headers dict with authorization and custom headers

        """
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        headers.update(self.headers)

        return headers

    async def deploy_agent(
        self,
        agent_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Deploy an agent to the backend.

        Args:
            agent_config: Agent configuration dict

        Returns:
            Deployment response with agent_id and status

        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/agents",
                json=agent_config,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_agent(
        self,
        agent_id: str,
    ) -> dict[str, Any]:
        """Get agent configuration from backend.

        Args:
            agent_id: ID of the agent

        Returns:
            Agent configuration dict

        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/agents/{agent_id}",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def delete_agent(
        self,
        agent_id: str,
    ) -> None:
        """Delete an agent from the backend.

        Args:
            agent_id: ID of the agent

        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/v1/agents/{agent_id}",
                headers=self._get_headers(),
            )
            response.raise_for_status()

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all agents in backend.

        Returns:
            List of agent configuration dicts

        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/agents",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def execute(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute an agent on the backend.

        Args:
            agent_id: ID of the agent to execute
            messages: Conversation messages
            tools: Optional tool definitions
            stream: Whether to stream the response

        Yields:
            Stream events from the backend

        """
        import json

        payload: dict[str, Any] = {"messages": messages}
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream"] = True

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/agents/{agent_id}/run",
                json=payload,
                headers=self._get_headers(),
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
                    elif line:
                        yield line

    async def health_check(self) -> bool:
        """Check if backend is healthy.

        Returns:
            True if healthy, False otherwise

        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


__all__ = ["BackendClient"]
