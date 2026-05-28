"""Backend client for remote agent management."""

import json

import httpx
from typing import Any, AsyncIterator


class BackendClient:
    """Internal client for backend communication.

    Used by Agent for deployed mode and standalone functions.
    Reuses a single ``httpx.AsyncClient`` instance for connection pooling.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        """Initialize Backend Client.

        Args:
            base_url: Base URL of the backend server
            api_key: API key for authentication
            email: Email for login (alternative to api_key)
            password: Password for login (alternative to api_key)
            headers: Custom headers for auth and multi-tenancy
            timeout: Request timeout in seconds

        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.email = email
        self.password = password
        self.headers = headers or {}
        self.timeout = timeout
        self._tenant_id: str | None = None
        self._user_id: str | None = None
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def login(self, **kwargs: Any) -> dict[str, Any]:
        """Login with credentials.

        Default fields: email, password
        Additional fields can be passed for custom auth (e.g., username, totp).

        Args:
            **kwargs: Login fields (email, password, etc.)

        Returns:
            Login response with token and tenant info

        Raises:
            httpx.HTTPStatusError: If login fails
        """
        if not kwargs:
            raise ValueError("login requires credentials (email/password or custom)")

        response = await self._client.post(
            "/v1/auth/login",
            json=kwargs,
        )
        response.raise_for_status()
        data = response.json()
        self.api_key = data.get("access_token")
        self._tenant_id = data.get("tenant_id")
        self._user_id = data.get("user_id")
        return data

    async def register(self, **kwargs: Any) -> dict[str, Any]:
        """Register a new user.

        Default fields: email, password, tenant_name
        Additional fields can be passed for custom registration (e.g., username, full_name).

        Args:
            **kwargs: Registration fields (email, password, tenant_name, etc.)

        Returns:
            Registration response with token and tenant info
        """
        if not kwargs:
            raise ValueError("register requires user information")

        response = await self._client.post(
            "/v1/auth/register",
            json=kwargs,
        )
        response.raise_for_status()
        data = response.json()
        self.api_key = data.get("access_token")
        self._tenant_id = data.get("tenant_id")
        self._user_id = data.get("user_id")
        return data

    @property
    def tenant_id(self) -> str | None:
        """Get logged in tenant ID."""
        return self._tenant_id

    @property
    def user_id(self) -> str | None:
        """Get logged in user ID."""
        return self._user_id

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
            agent_config: Agent configuration dict with 'agent' and 'tools' keys

        Returns:
            Deployment response with agent_id and status

        """
        # Extract the agent config from the nested structure
        # The SDK sends { "agent": {...}, "tools": [...] }
        # Backend expects { "name": str, "config": dict }

        # Handle both old format (direct) and new format (nested)
        if "agent" in agent_config:
            agent_data = agent_config["agent"]
            name = agent_data.get("name", "agent")
            config = {k: v for k, v in agent_data.items() if k != "name"}
        else:
            name = agent_config.get("name", "agent")
            config = {k: v for k, v in agent_config.items() if k != "name"}

        payload = {
            "name": name,
            "config": config,
        }

        response = await self._client.post(
            "/v1/agents",
            json=payload,
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
        response = await self._client.get(
            f"/v1/agents/{agent_id}",
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
        response = await self._client.delete(
            f"/v1/agents/{agent_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all agents in backend.

        Returns:
            List of agent configuration dicts

        """
        response = await self._client.get(
            "/v1/agents",
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
        plan_mode: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute an agent on the backend.

        Args:
            agent_id: ID of the agent to execute
            messages: Conversation messages
            tools: Optional tool definitions
            stream: Whether to stream the response
            plan_mode: If True, only allow plan-mode tools

        Yields:
            Stream events from the backend

        """
        user_input = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_input = msg.get("content", "")
                break

        payload: dict[str, Any] = {"user_input": user_input, "plan_mode": plan_mode}
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream"] = True

        async with self._client.stream(
            "POST",
            f"/v1/agents/{agent_id}/run",
            json=payload,
            headers=self._get_headers(),
        ) as response:
            async for line in response.aiter_lines():
                line = line.strip()
                if line:
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass

    async def health_check(self) -> bool:
        """Check if backend is healthy.

        Returns:
            True if healthy, False otherwise

        """
        try:
            response = await self._client.get("/health", timeout=5)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools in backend with versions.

        Returns:
            List of tool dicts including version

        """
        response = await self._client.get(
            "/v1/tools",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_tool(self, tool_id: str) -> dict[str, Any]:
        """Get a specific tool by ID.

        Args:
            tool_id: ID of the tool

        Returns:
            Tool dict with all fields

        """
        response = await self._client.get(
            f"/v1/tools/{tool_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def deploy_tool(self, tool_bundle: dict[str, Any]) -> dict[str, Any]:
        """Deploy a tool bundle to backend.

        Args:
            tool_bundle: Tool bundle from Tool.to_bundle()

        Returns:
            Tool response with ID and version

        """
        response = await self._client.post(
            "/v1/tools",
            json=tool_bundle,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def guest_run(
        self,
        agent_id: str,
        user_input: str,
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run an agent as guest (no auth required).

        Guest sessions are:
        - Temporary (in-memory, not persisted)
        - Shared among all guest users
        - Auto-expire after 30 minutes of inactivity

        Args:
            agent_id: ID of the agent to execute
            user_input: User input message
            session_id: Optional session ID for continuing a session

        Yields:
            Stream events from the backend

        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "user_input": user_input,
        }
        if session_id:
            payload["session_id"] = session_id

        async with self._client.stream(
            "POST",
            "/guest/run",
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])
                elif line:
                    yield line

    async def create_session(
        self,
        agent_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new session.

        Args:
            agent_id: ID of the agent for this session
            name: Optional session name

        Returns:
            Session response with id, agent_id, name, created_at, updated_at

        """
        response = await self._client.post(
            "/v1/sessions",
            json={"name": name},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions in backend.

        Returns:
            List of session dicts with id, agent_id, name, created_at, updated_at

        """
        response = await self._client.get(
            "/v1/sessions",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def update_session(
        self,
        session_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing session.

        Args:
            session_id: ID of the session to update
            name: Optional new session name

        Returns:
            Updated session response

        """
        response = await self._client.patch(
            f"/v1/sessions/{session_id}",
            json={"name": name} if name else {},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get messages for a session.

        Args:
            session_id: ID of the session
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of message dicts with id, role, content, turn_index, created_at

        """
        response = await self._client.get(
            f"/v1/sessions/{session_id}/messages",
            params={"limit": limit, "offset": offset},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> dict[str, Any]:
        """Add a message to a session.

        Args:
            session_id: ID of the session
            role: Message role (user, assistant, tool, metadata)
            content: Message content

        Returns:
            Message response with id, role, content, turn_index, created_at

        """
        response = await self._client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"role": role, "content": content},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Get a complete session by ID.

        Args:
            session_id: ID of the session

        Returns:
            Session dict with id, agent_id, name, messages, created_at, updated_at, version

        """
        response = await self._client.get(
            f"/v1/sessions/{session_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def sync_memory(
        self,
        agent_id: str,
        memory: dict[str, Any],
    ) -> dict[str, Any]:
        """Sync agent memory to backend.

        Args:
            agent_id: ID of the agent
            memory: Memory data to sync

        Returns:
            Sync response with status and timestamp

        """
        response = await self._client.post(
            f"/v1/agents/{agent_id}/memory",
            json=memory,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_memory(
        self,
        agent_id: str,
    ) -> dict[str, Any]:
        """Get agent memory from backend.

        Args:
            agent_id: ID of the agent

        Returns:
            Memory data dict

        """
        response = await self._client.get(
            f"/v1/agents/{agent_id}/memory",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def save_memory(
        self,
        agent_id: str,
        memory: dict[str, Any],
    ) -> dict[str, Any]:
        """Save agent memory to backend.

        Args:
            agent_id: ID of the agent
            memory: Memory data to save

        Returns:
            Response data

        """
        response = await self._client.put(
            f"/v1/agents/{agent_id}/memory",
            json=memory,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()


__all__ = ["BackendClient"]
