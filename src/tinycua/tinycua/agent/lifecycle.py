"""Agent lifecycle management for backend operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tinycua.clients.backend import BackendClient

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent

logger = logging.getLogger(__name__)


class AgentLifecycle:
    """Manages agent lifecycle operations with the backend.

    Handles deploy, delete, load, and guest mode operations
    for agents that interact with a backend server.
    """

    def __init__(
        self,
        agent: Agent,
        backend_url: str | None = None,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
    ):
        """Initialize with an Agent instance.

        Args:
            agent: Agent instance to manage lifecycle for.
            backend_url: Backend URL (falls back to agent config, then env).
            backend_api_key: API key for authentication.
            backend_headers: Custom headers for auth and multi-tenancy.

        """
        self.agent = agent
        self._backend_url = backend_url
        self._backend_api_key = backend_api_key
        self._backend_headers = backend_headers

    def _get_backend_config(self) -> tuple[str, str | None, dict[str, str] | None]:
        """Get backend configuration with priority.

        Returns:
            Tuple of (backend_url, api_key, headers).

        """
        from tinycua_sdk.core.config import SDKConfig

        config = SDKConfig.load()

        backend_url = (
            self._backend_url or self.agent.config.backend_url or config.backend_url
        )
        api_key = (
            self._backend_api_key
            or self.agent.config.backend_api_key
            or config.llm.api_key.get_secret_value()
            if config.llm.api_key
            else None
        )
        headers = self._backend_headers or self.agent.config.backend_headers

        return backend_url, api_key, headers

    async def deploy(self) -> dict[str, Any]:
        """Deploy the agent and its tools to the backend.

        Mutates self.agent.config.mode to "deployed" and
        self.agent.config.agent_id with the returned ID.

        Returns:
            Deployment result with agent_id and status.

        Raises:
            RuntimeError: If circular dependency detected.

        """
        from tinycua_sdk.tools.resolver import (
            analyze_source,
            compute_version,
            detect_circular,
            find_internal_calls,
            topological_sort,
        )

        backend_url, backend_api_key, backend_headers = self._get_backend_config()

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=backend_headers,
        )

        tools = list(self.agent.config.tools)
        tool_names = {t.name for t in tools}

        existing_tools: dict[str, dict[str, Any]] = {}
        try:
            backend_tools = await client.list_tools()
            for t in backend_tools:
                existing_tools[t.get("name", "")] = t
        except Exception:
            pass

        for tool in tools:
            if tool._source:
                external_deps = analyze_source(tool._source)
                tool._external_dependencies = external_deps

                internal_calls = find_internal_calls(tool._source)
                tool_deps = []
                for call_name in internal_calls:
                    if call_name in tool_names and call_name != tool.name:
                        dep_tool = next((t for t in tools if t.name == call_name), None)
                        if dep_tool:
                            tool_deps.append(
                                {
                                    "id": getattr(dep_tool, "_id", ""),
                                    "name": call_name,
                                    "version": getattr(dep_tool, "_version", ""),
                                }
                            )
                tool._tool_dependencies = tool_deps

                tool._version = compute_version(
                    tool._source or "",
                    tool._tool_dependencies,
                )

        tool_map = {t.name: t for t in tools}
        cycle = detect_circular(tools, tool_map)
        if cycle:
            cycle_str = " -> ".join(cycle)
            raise RuntimeError(f"Circular dependency detected: {cycle_str}")

        sorted_tools = topological_sort(tools)

        tools_to_upload = []
        for tool in sorted_tools:
            existing = existing_tools.get(tool.name, {})
            if existing.get("version") != tool._version:
                tools_to_upload.append(tool)

        for tool in tools_to_upload:
            bundle = tool.to_bundle()
            try:
                await client.deploy_tool(bundle)
            except Exception as e:
                raise RuntimeError(f"Failed to deploy tool {tool.name}: {e}")

        deployment = {
            "agent": self.agent.to_config(),
            "tools": [],
        }

        for tool in self.agent.config.tools:
            deployment["tools"].append(
                {
                    "name": tool.name,
                    "bundle": tool.to_bundle(),
                }
            )

        response = await client.deploy_agent(agent_config=deployment)

        self.agent.config.mode = "deployed"
        self.agent.config.agent_id = response["id"]
        self.agent.config.backend_url = backend_url

        return response

    async def delete(self) -> None:
        """Delete the agent from the backend.

        Mutates self.agent.config.agent_id to None and
        self.agent.config.mode to "local".

        Raises:
            RuntimeError: If agent is not deployed.

        """
        if not self.agent.config.agent_id:
            raise RuntimeError("Agent not deployed")

        backend_url, backend_api_key, backend_headers = self._get_backend_config()

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=backend_headers,
        )

        await client.delete_agent(agent_id=self.agent.config.agent_id)

        self.agent.config.agent_id = None
        self.agent.config.mode = "local"

    def set_guest_mode(self, agent_id: str, backend_url: str | None = None) -> None:
        """Set agent to guest mode.

        Mutates self.agent.config.mode to "guest" and
        self.agent.config.agent_id to the provided agent_id.

        Args:
            agent_id: ID of a deployed agent to use in guest mode.
            backend_url: Optional backend URL (defaults to config).

        """
        from tinycua_sdk.core.config import SDKConfig

        global_config = SDKConfig.load()
        global_backend_url = global_config.backend_url

        self.agent.config.mode = "guest"
        self.agent.config.agent_id = agent_id
        self.agent.config.backend_url = backend_url or global_backend_url

    @classmethod
    async def load_agent(
        cls,
        agent_id: str,
        backend_url: str,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
    ) -> Agent:
        """Load an existing agent from the backend.

        Tool resolution:
        1. Fetches agent config from backend (includes tool configs).
        2. Creates Agent via Agent.from_config().
        3. Tools are reconstructed from config via Tool.from_config().
        4. If a tool referenced by the agent is not available locally,
           it is reconstructed from its stored bundle (source + dependencies).
        5. Missing tools that cannot be reconstructed are logged as warnings
           but do not prevent agent loading.

        Args:
            agent_id: ID of the agent to load.
            backend_url: Backend server URL.
            backend_api_key: API key for authentication.
            backend_headers: Custom headers for auth.

        Returns:
            Agent instance with configuration from backend, mode="deployed".

        """
        from tinycua_sdk.agent.agent import Agent

        client = BackendClient(
            base_url=backend_url,
            api_key=backend_api_key,
            headers=backend_headers,
        )

        agent_data = await client.get_agent(agent_id)

        agent = Agent.from_config(agent_data)
        agent.config.agent_id = agent_id
        agent.config.mode = "deployed"
        agent.config.backend_url = backend_url

        return agent
