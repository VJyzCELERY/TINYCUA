"""Agent definition with config, properties, and serialization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent


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
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        tools: list[Tool] | None = None,
        policy: AgentPolicy | None = None,
        mode: str = "local",
        backend_url: str | None = None,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
        agent_id: str | None = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        current_depth: int = 0,
        keywords: list[str] | None = None,
        strip_thinking: bool | list[str] | None = None,
        loop: Any = None,
        skills: list[str] | None = None,
        planning_prompt: str | None = None,
    ):
        """Initialize AgentDefinition.

        Args:
            name: Agent name for identification.
            instructions: Additional instructions for the agent.
            system_prompt: System prompt that defines agent behavior.
            model: Model identifier to use.
            provider: LLM provider type. Use "openai" for OpenAI API
                or "openai-compatible" for any OpenAI-compatible endpoint
                (e.g., local inference servers). Aliases "lmstudio" and
                "ollama" are supported for backward compatibility.
            base_url: Custom base URL for the LLM API.
            api_key: API key for authentication.
            tools: List of tools available to the agent.
            policy: AgentPolicy instance for behavior settings.
            mode: Execution mode (local or remote/deployed).
            backend_url: URL for the backend server (for deployed agents).
            backend_api_key: API key for backend authentication.
            backend_headers: Additional headers for backend requests.
            agent_id: ID of a deployed agent (for loading existing agents).
            sub_agents: List of sub-agents for delegation.
            max_depth: Maximum delegation depth allowed.
            current_depth: Current delegation depth (internal).
            keywords: Keywords for task routing to this agent.
            strip_thinking: Whether to strip thinking tags from responses.
            loop: Custom DefaultLoop subclass instance.
            skills: List of skill names to load for the agent.
            planning_prompt: Prompt for task planning/analysis.

        """
        self.config = AgentConfig(
            name=name,
            instructions=instructions,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            tools=tools or [],
            policy=policy or AgentPolicy(),
            mode=mode,
            backend_url=backend_url,
            backend_api_key=backend_api_key,
            backend_headers=backend_headers,
            agent_id=agent_id,
            strip_thinking=strip_thinking,
            sub_agents=sub_agents or [],
            loop=loop,
            skills=skills or [],
            planning_prompt=planning_prompt,
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
    def mode(self) -> str:
        """Get agent mode (local or deployed)."""
        return self.config.mode

    @property
    def agent_id(self) -> str | None:
        """Get deployed agent ID."""
        return self.config.agent_id

    @property
    def is_deployed(self) -> bool:
        """Check if agent is in deployed mode."""
        return self.config.mode == "deployed"

    @property
    def instructions(self) -> str:
        """Get agent instructions."""
        return self.config.instructions

    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return self.config.system_prompt

    @property
    def model(self) -> str:
        """Get model name."""
        return self.config.model

    @property
    def provider(self) -> str:
        """Get provider name."""
        return self.config.provider

    @property
    def tools(self) -> list[Tool]:
        """Get agent tools."""
        return self.config.tools

    @property
    def planning_prompt(self) -> str | None:
        """Get planning prompt for task analysis."""
        return self.config.planning_prompt

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
            system_prompt=config.system_prompt,
            model=config.model,
            provider=config.provider,
            base_url=config.base_url,
            api_key=config.api_key,
            tools=config.tools,
            policy=config.policy,
            mode=config.mode,
            backend_url=config.backend_url,
            backend_api_key=config.backend_api_key,
            backend_headers=config.backend_headers,
            agent_id=config.agent_id,
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
            f"  Mode: {self.config.mode}",
            f"  Model: {self.config.model}",
            f"  Provider: {self.config.provider}",
        ]
        if self.config.agent_id:
            lines.append(f"  Agent ID: {self.config.agent_id}")
            lines.append(f"  Backend: {self.config.backend_url}")
        if self.config.backend_headers:
            lines.append(f"  Headers: {list(self.config.backend_headers.keys())}")
        lines.append(f"  Tools: {len(self.config.tools)}")
        lines.append(f"  Sub-agents: {len(self.config.sub_agents)}")
        return "\n".join(lines)
