"""Backend protocol interface for type hints.

This protocol defines the interface expected from backend clients.
It is provided for future type-hint use and is not actively used
by SDK code in this stage.
"""

from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class BackendProtocol(Protocol):
    """Protocol for backend clients.

    Defines the interface that backend client implementations must provide.
    """

    base_url: str

    async def deploy_agent(self, agent_config: dict) -> dict:
        """Deploy an agent with the given configuration."""
        ...

    async def get_agent(self, agent_id: str) -> dict:
        """Get agent configuration by ID."""
        ...

    async def delete_agent(self, agent_id: str) -> None:
        """Delete an agent by ID."""
        ...

    async def list_agents(self) -> list[dict]:
        """List all agents in the backend."""
        ...

    async def execute(
        self,
        agent_id: str,
        messages: list[dict],
        tools: list[dict] | None,
        stream: bool,
    ) -> AsyncIterator[dict]:
        """Execute an agent with the given messages."""
        ...

    async def health_check(self) -> bool:
        """Check backend health status."""
        ...

    async def list_tools(self) -> list[dict]:
        """List all available tools."""
        ...

    async def deploy_tool(self, tool_bundle: dict) -> dict:
        """Deploy a tool bundle to the backend."""
        ...

    async def guest_run(
        self,
        agent_id: str,
        user_input: str,
        session_id: str | None,
    ) -> AsyncIterator[dict]:
        """Run an agent as guest (no auth required)."""
        ...
