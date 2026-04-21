"""Agent manager for TinyCUA TUI."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent

logger = logging.getLogger(__name__)

AGENTS_DIR = Path.home() / ".tinycua" / "agents"


@dataclass
class AgentInfo:
    """Agent information for TUI.

    Attributes:
        id: Agent UUID.
        name: Agent name.
        config: Agent configuration.
    """

    id: uuid.UUID
    name: str
    config: AgentConfig


class AgentManager:
    """Agent manager for TUI.

    Provides CRUD operations for agents, agent initialization,
    and agent instance creation.
    """

    def __init__(self) -> None:
        """Initialize the agent manager."""
        self._agents: dict[uuid.UUID, AgentInfo] = {}
        self._current_agent_id: uuid.UUID | None = None
        self._default_agent: Agent | None = None
        self._ensure_agents_dir()

    def _ensure_agents_dir(self) -> None:
        """Ensure agents directory exists."""
        try:
            AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("Failed to create agents directory")

    def _get_agent_file(self, agent_id: uuid.UUID) -> Path:
        """Get the file path for an agent config.

        Args:
            agent_id: Agent UUID.

        Returns:
            Path to agent config file.
        """
        return AGENTS_DIR / f"{agent_id}.json"

    def create_agent(
        self,
        name: str,
        model: str = "gpt-5-nano",
        provider: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        system_prompt: str = "You are a helpful assistant.",
        instructions: str = "",
        temperature: float = 1.0,
        max_turns: int | None = None,
    ) -> AgentInfo | None:
        """Create a new agent.

        Args:
            name: Agent name.
            model: Model to use.
            provider: Provider to use.
            base_url: Optional base URL for provider.
            api_key: Optional API key.
            system_prompt: System prompt.
            instructions: Agent instructions.
            temperature: Temperature parameter for agent responses.
            max_turns: Maximum number of conversation turns.

        Returns:
            Created AgentInfo or None on error.
        """
        try:
            agent_id = uuid.uuid4()
            policy = AgentPolicy(temperature=temperature)
            metadata = {"max_turns": max_turns} if max_turns is not None else {}
            config = AgentConfig(
                name=name,
                model=model,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                system_prompt=system_prompt,
                instructions=instructions,
                policy=policy,
                metadata=metadata,
            )
            agent_info = AgentInfo(
                id=agent_id,
                name=name,
                config=config,
            )
            self._save_agent(agent_info)
            self._agents[agent_id] = agent_info
            return agent_info
        except Exception:
            logger.exception("Failed to create agent")
            return None

    def _save_agent(self, agent_info: AgentInfo) -> None:
        """Save agent config to file.

        Args:
            agent_info: Agent information to save.
        """
        file_path = self._get_agent_file(agent_info.id)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(agent_info.config.to_json())
        except Exception:
            logger.exception("Failed to save agent config")

    def get_agent(self, agent_id: uuid.UUID) -> AgentInfo | None:
        """Get an agent by ID.

        Args:
            agent_id: Agent UUID.

        Returns:
            AgentInfo or None if not found.
        """
        if agent_id in self._agents:
            return self._agents[agent_id]

        file_path = self._get_agent_file(agent_id)
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text())
            config = AgentConfig.from_config(data)
            agent_info = AgentInfo(
                id=agent_id,
                name=config.name,
                config=config,
            )
            self._agents[agent_id] = agent_info
            return agent_info
        except Exception:
            logger.exception("Failed to load agent config")
            return None

    def list_agents(self) -> list[AgentInfo]:
        """List all agents.

        Returns:
            List of AgentInfo instances.
        """
        try:
            AGENTS_DIR.mkdir(parents=True, exist_ok=True)
            for file_path in AGENTS_DIR.glob("*.json"):
                try:
                    agent_id = uuid.UUID(file_path.stem)
                    if agent_id not in self._agents:
                        self.get_agent(agent_id)
                except Exception:
                    continue
        except Exception:
            logger.exception("Failed to list agents")
        return list(self._agents.values())

    def update_agent(
        self,
        agent_id: uuid.UUID,
        name: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        system_prompt: str | None = None,
        instructions: str | None = None,
    ) -> AgentInfo | None:
        """Update an existing agent.

        Args:
            agent_id: Agent UUID.
            name: New name (optional).
            model: New model (optional).
            provider: New provider (optional).
            base_url: New base URL (optional).
            api_key: New API key (optional).
            system_prompt: New system prompt (optional).
            instructions: New instructions (optional).

        Returns:
            Updated AgentInfo or None if not found.
        """
        agent_info = self.get_agent(agent_id)
        if agent_info is None:
            return None

        try:
            config = agent_info.config
            if name is not None:
                config.name = name
                agent_info.name = name
            if model is not None:
                config.model = model
            if provider is not None:
                config.provider = provider
            if base_url is not None:
                config.base_url = base_url
            if api_key is not None:
                config.api_key = api_key
            if system_prompt is not None:
                config.system_prompt = system_prompt
            if instructions is not None:
                config.instructions = instructions

            agent_info.config = config
            self._save_agent(agent_info)
            return agent_info
        except Exception:
            logger.exception("Failed to update agent")
            return None

    def delete_agent(self, agent_id: uuid.UUID) -> bool:
        """Delete an agent.

        Args:
            agent_id: Agent UUID.

        Returns:
            True if deleted, False otherwise.
        """
        file_path = self._get_agent_file(agent_id)
        try:
            if file_path.exists():
                file_path.unlink()
            if agent_id in self._agents:
                del self._agents[agent_id]
            if self._current_agent_id == agent_id:
                self._current_agent_id = None
            return True
        except Exception:
            logger.exception("Failed to delete agent")
            return False

    def set_current_agent(self, agent_id: uuid.UUID) -> bool:
        """Set the current active agent.

        Args:
            agent_id: Agent UUID to set as current.

        Returns:
            True if successful, False otherwise.
        """
        agent_info = self.get_agent(agent_id)
        if agent_info is None:
            return False
        self._current_agent_id = agent_id
        return True

    def get_current_agent(self) -> AgentInfo | None:
        """Get the current active agent.

        Returns:
            Current AgentInfo or None.
        """
        if self._current_agent_id is None:
            return None
        return self.get_agent(self._current_agent_id)

    def init_default_agent(self) -> Agent | None:
        """Initialize the default agent using SDK.

        Returns:
            Initialized Agent instance or None on error.
        """
        from tinycua.agent.default_agent import create_default_agent

        try:
            self._default_agent = create_default_agent()
            return self._default_agent
        except Exception:
            logger.exception("Failed to initialize default agent")
            return None

    def create_agent_instance(
        self, agent_info: AgentInfo
    ) -> Agent | None:
        """Create an Agent instance from AgentInfo.

        Args:
            agent_info: Agent configuration info.

        Returns:
            Agent instance or None on error.
        """
        from tinycua_sdk.agent.agent import Agent

        try:
            config = agent_info.config
            return Agent(
                name=config.name,
                system_prompt=config.system_prompt,
                model=config.model,
                provider=config.provider,
                base_url=config.base_url,
                api_key=config.api_key,
                tools=config.tools,
                policy=config.policy,
                mode=config.mode,
            )
        except Exception:
            logger.exception("Failed to create agent instance")
            return None

    def get_default_agent(self) -> Agent | None:
        """Get the default agent instance.

        Returns:
            Agent instance or None.
        """
        return self._default_agent
