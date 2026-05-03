"""Agent definition with config, properties, and serialization."""

from __future__ import annotations

from typing import Any

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.tools.decorators import Tool




class AgentDefinition:
    """Base class holding agent configuration and properties.

    Provides config management, property accessors, tool management,
    serialization, and string representation.
    """

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LLMModel | None = None,
        tools: list[Tool] | None = None,
        skills: list[Any] | None = None,
        policy: AgentPolicy | None = None,
        loop: Any = None,
    ):
        """Initialize AgentDefinition.

        Args:
            name: Agent name for identification.
            instructions: Additional instructions for the agent.
            llm_model: LLM endpoint configuration.
            tools: List of tools available to the agent.
            skills: List of skills available to the agent.
            policy: AgentPolicy instance for behavior settings.
            loop: Custom BaseLoop subclass instance.

        """
        self.config = AgentConfig(
            name=name,
            instructions=instructions,
            llm_model=llm_model or LLMModel(),
            tools=tools or [],
            skills=skills or [],
            policy=policy or AgentPolicy(),
            loop=loop,
        )

    # --- Property accessors (delegate to config) ---

    @property
    def policy(self) -> AgentPolicy:
        """Get agent policy."""
        return self.config.policy

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.config.name

    @property
    def instructions(self) -> str:
        """Get agent instructions."""
        return self.config.instructions

    @property
    def llm_model(self) -> LLMModel:
        """Get LLM model configuration."""
        return self.config.llm_model

    @llm_model.setter
    def llm_model(self, value: LLMModel) -> None:
        """Set LLM model configuration."""
        self.config.llm_model = value

    @property
    def system_prompt(self) -> str:
        """Get system prompt from LLM model."""
        return self.config.llm_model.system_prompt

    @property
    def model(self) -> str:
        """Get model name from LLM model."""
        return self.config.llm_model.model_name

    @property
    def provider(self) -> str:
        """Get provider name from LLM model."""
        return self.config.llm_model.provider

    @property
    def base_url(self) -> str | None:
        """Get base URL from LLM model."""
        return self.config.llm_model.base_url

    @property
    def api_key(self) -> str:
        """Get API key from LLM model."""
        return self.config.llm_model.api_key.get_secret_value()

    @property
    def tools(self) -> list[Tool]:
        """Get agent tools."""
        return self.config.tools

    @property
    def skills(self) -> list[Any]:
        """Get agent skills."""
        return self.config.skills

    @property
    def loop(self) -> Any:
        """Get agent loop."""
        return self.config.loop

    # --- Tool management ---

    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the agent."""
        self.config.tools.append(tool)

    def add_tools(self, tools: list[Tool]) -> None:
        """Add multiple tools to the agent."""
        self.config.tools.extend(tools)

    # --- Serialization ---

    def to_config(self) -> dict[str, Any]:
        """Serialize agent config to dict."""
        return self.config.to_config()

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> AgentDefinition:
        """Create agent from config dict."""
        config = AgentConfig.from_config(data)
        agent = cls(
            name=config.name,
            instructions=config.instructions,
            llm_model=config.llm_model,
            tools=config.tools,
            skills=config.skills,
            policy=config.policy,
            loop=config.loop,
        )
        return agent

    def __str__(self) -> str:
        """Return formatted string representation of the agent."""
        lines = [
            f"Agent: {self.config.name}",
            f"  Model: {self.config.llm_model.model_name}",
            f"  Provider: {self.config.llm_model.provider}",
        ]
        lines.append(f"  Tools: {len(self.config.tools)}")
        return "\n".join(lines)
