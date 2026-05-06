"""Agent with lifecycle convenience wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_model import LanguageModel

if TYPE_CHECKING:
    from tinycua_sdk.agent.loop import BaseLoop
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.skills.models import Skill


class Agent(AgentExecutor):
    """Stateless, fully runnable agent class."""

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LanguageModel | None = None,
        tools: list[Tool] | None = None,
        skills: list[Skill] | None = None,
        policy: AgentPolicy | None = None,
        metadata: dict | None = None,
        loop: BaseLoop | None = None,
        tool_permissions: dict[str, Literal["allow", "ask", "deny"]] | None = None,
        approval_workflow: Any | None = None,
    ):
        config = AgentConfig(
            name=name,
            instructions=instructions,
            llm_model=llm_model or LanguageModel(),
            tools=tools or [],
            skills=skills or [],
            policy=policy or AgentPolicy(),
            metadata=metadata or {},
            loop=loop,
            tool_permissions=tool_permissions or {},
            approval_workflow=approval_workflow,
        )

        super().__init__(config=config)

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.config.name

    @property
    def instructions(self) -> str:
        """Get agent instructions."""
        return self.config.instructions

    @property
    def llm_model(self) -> LanguageModel:
        """Get LLM model configuration."""
        return self.config.llm_model

    @property
    def tools(self) -> list[Tool]:
        """Get agent tools."""
        return self.config.tools

    @property
    def skills(self) -> list[Skill]:
        """Get agent skills."""
        return self.config.skills

    @property
    def policy(self) -> AgentPolicy:
        """Get agent policy."""
        return self.config.policy

    @property
    def metadata(self) -> dict:
        """Get agent metadata."""
        return self.config.metadata

    @property
    def loop(self) -> Any:
        """Get agent loop."""
        return self.config.loop

    @property
    def tool_permissions(self) -> dict[str, Literal["allow", "ask", "deny"]]:
        """Get tool permissions."""
        return self.config.tool_permissions

    @tool_permissions.setter
    def tool_permissions(
        self, value: dict[str, Literal["allow", "ask", "deny"]]
    ) -> None:
        """Set tool permissions."""
        self.config.tool_permissions = value

    @property
    def approval_workflow(self) -> Any:
        """Get approval workflow."""
        return self.config.approval_workflow

    def add_tools(self, tool_or_list: Tool | list[Tool]) -> None:
        """Append one or more tools to the agent.

        Args:
            tool_or_list: A single Tool or a list of Tools.
        """
        if isinstance(tool_or_list, list):
            self.config.tools.extend(tool_or_list)
        else:
            self.config.tools.append(tool_or_list)

    def add_skills(self, skill_or_list: Skill | list[Skill]) -> None:
        """Append one or more skills to the agent.

        Args:
            skill_or_list: A single Skill or a list of Skills.
        """
        if isinstance(skill_or_list, list):
            self.config.skills.extend(skill_or_list)
        else:
            self.config.skills.append(skill_or_list)

    def to_config(self) -> dict[str, Any]:
        """Serialize agent to a configuration dict.

        Returns:
            Dictionary representation of the agent.
        """
        return self.config.to_config()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Agent":
        """Create an agent from a configuration dict.

        Args:
            config: A configuration dictionary.

        Returns:
            A new Agent instance.
        """
        agent_config = AgentConfig.from_config(config)
        return cls(
            name=agent_config.name,
            instructions=agent_config.instructions,
            llm_model=agent_config.llm_model,
            tools=agent_config.tools,
            skills=agent_config.skills,
            policy=agent_config.policy,
            metadata=agent_config.metadata,
            loop=agent_config.loop,
            tool_permissions=agent_config.tool_permissions,
            approval_workflow=agent_config.approval_workflow,
        )


__all__ = ["Agent"]
