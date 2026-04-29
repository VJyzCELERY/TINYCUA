"""Agent definition with config, properties, and serialization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.backend_kind import BackendConfig
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.agent.loop import BaseLoop
    from tinycua_sdk.skills.models import Skill


class AgentDefinition:
    """Base class holding agent configuration and properties.

    Provides config management, property accessors, sub-agent management,
    tool management, serialization, and string representation.
    """

    MAX_SUB_AGENTS = 10
    DEFAULT_MAX_DEPTH = 3

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LLMModel | None = None,
        tools: list[Tool] | None = None,
        skills: list[Any] | None = None,
        policy: AgentPolicy | None = None,
        backend: BackendConfig | None = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        current_depth: int = 0,
        keywords: list[str] | None = None,
        strip_thinking: bool | list[str] | None = None,
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
            backend: Backend execution configuration.
            sub_agents: List of sub-agents for delegation.
            max_depth: Maximum delegation depth allowed.
            current_depth: Current delegation depth (internal).
            keywords: Keywords for task routing to this agent.
            strip_thinking: Whether to strip thinking tags from responses.
            loop: Custom BaseLoop subclass instance.

        """
        self.config = AgentConfig(
            name=name,
            instructions=instructions,
            llm_model=llm_model or LLMModel(),
            tools=tools or [],
            skills=skills or [],
            policy=policy or AgentPolicy(),
            backend=backend or BackendConfig(),
            sub_agents=sub_agents or [],
            max_depth=max_depth,
            strip_thinking=strip_thinking,
            loop=loop,
        )
        self._sub_agents = sub_agents or []
        self.max_depth = max_depth
        self.current_depth = current_depth
        self.keywords = keywords or []

    # --- Property accessors (delegate to config) ---

    @property
    def sub_agents(self) -> list[Agent]:
        """Get list of sub-agents."""
        return self.config.sub_agents

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
    def backend(self) -> BackendConfig:
        """Get backend configuration."""
        return self.config.backend

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

    @property
    def strip_thinking(self) -> bool | list[str] | None:
        """Get strip thinking configuration."""
        return self.config.strip_thinking

    # --- Sub-agent management ---

    def add_sub_agent(self, agent: Agent) -> None:
        """Add a sub-agent to this agent.

        Args:
            agent: The sub-agent to add.

        Raises:
            ValueError: If max sub-agents limit exceeded.

        """
        if len(self.config.sub_agents) >= self.MAX_SUB_AGENTS:
            raise ValueError(
                f"Maximum {self.MAX_SUB_AGENTS} sub-agents allowed per agent"
            )
        self.config.sub_agents.append(agent)
        self._sub_agents = self.config.sub_agents

    def _get_all_sub_agents(self, depth: int = 0) -> dict[str, Any]:
        """Get all sub-agents recursively."""
        if depth >= self.max_depth:
            return {self.name: self}
        result: dict[str, Any] = {self.name: self}
        for sub in self._sub_agents:
            result.update(sub._get_all_sub_agents(depth + 1))
        return result

    def _find_sub_agent_for_task(self, task: str) -> Any:
        """Find a sub-agent that can handle the task based on keywords."""
        task_lower = task.lower()
        for sub in self._sub_agents:
            sub_keywords = sub.keywords or [sub.name.lower()]
            if any(kw.lower() in task_lower for kw in sub_keywords):
                return sub
        return None

    def _pass_context_to_sub_agent(self, task: str, sub_agent: Agent) -> str:
        """Pass context to sub-agent."""
        return (
            f"\nParent Task: {task}\nParent Agent: {self.name}\n"
            f"Instructions: {self.instructions}\n\n"
            "Please complete this task and return results.\n"
        )

    def _aggregate_results(self, sub_result: str, sub_agent: Agent) -> str:
        """Aggregate results from sub-agent."""
        return (
            f"\n[Sub-agent: {sub_agent.name}]\nResult: {sub_result}\n\n"
            f"Summary: Completed via delegation to {sub_agent.name}\n"
        )

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
            backend=config.backend,
            sub_agents=config.sub_agents,
            max_depth=data.get("max_depth", cls.DEFAULT_MAX_DEPTH),
            current_depth=data.get("current_depth", 0),
            keywords=data.get("keywords", []),
            strip_thinking=config.strip_thinking,
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
        lines.append(f"  Sub-agents: {len(self.config.sub_agents)}")
        return "\n".join(lines)
