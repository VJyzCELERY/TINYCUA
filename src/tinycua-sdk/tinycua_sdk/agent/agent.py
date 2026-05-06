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


_OBSOLETE_PARAMS = frozenset(
    {
        "system_prompt",
        "model",
        "provider",
        "base_url",
        "api_key",
        "mode",
        "backend_url",
        "backend_api_key",
        "backend_headers",
        "agent_id",
        "planning_prompt",
        "short_term_memory",
        "long_term_memory",
        "session_id",
        "sub_agents",
        "max_depth",
        "strip_thinking",
        "backend",
    }
)


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
        **kwargs,
    ):
        """Initialize the Agent.

        Args:
            name: Agent name for identification.
            instructions: Additional instructions for the agent.
            llm_model: LLM endpoint configuration.
            tools: List of tools available to the agent.
            skills: List of skills available to the agent.
            policy: AgentPolicy instance for behavior settings.
            metadata: Optional metadata dict.
            loop: Custom BaseLoop subclass instance.
            tool_permissions: Tool permission map.
            approval_workflow: Optional approval workflow.
            **kwargs: Additional keyword arguments (unused).

        Raises:
            TypeError: If unknown parameters are passed.

        """
        for key in kwargs:
            if key in _OBSOLETE_PARAMS:
                raise TypeError(
                    f"Agent() got an unexpected keyword argument '{key}'. "
                    "This parameter has been removed in v2."
                )
        if kwargs:
            raise TypeError(
                "Agent() got unexpected keyword argument(s): "
                f"{', '.join(sorted(kwargs.keys()))}"
            )

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
    def from_config(cls, config: str | Any) -> "Agent":
        """Create an agent from a configuration dict, JSON file path, or YAML file path.

        Args:
            config: A dict, Path, or str path to a JSON/YAML file.

        Returns:
            A new Agent instance.
        """
        from pathlib import Path

        if isinstance(config, (str, Path)):
            path = Path(config)
            if path.suffix.lower() in (".yaml", ".yml"):
                from tinycua_sdk.agent.config import AgentConfig
                data = AgentConfig.from_yaml_file(path).to_config()
            else:
                from tinycua_sdk.agent.config import AgentConfig
                data = AgentConfig.from_json_file(path).to_config()
        elif isinstance(config, dict):
            data = config
        else:
            raise ValueError(f"Unsupported config type: {type(config)}")

        # Resolve nested value objects
        llm_data = data.get("llm_model", {})
        llm_model = LanguageModel.from_dict(llm_data) if isinstance(llm_data, dict) else LanguageModel()

        tools = data.get("tools", [])
        from tinycua_sdk.tools.decorators import Tool
        resolved_tools = []
        for t in tools:
            if isinstance(t, Tool):
                resolved_tools.append(t)
            elif isinstance(t, dict):
                resolved_tools.append(Tool.from_dict(t))
            else:
                resolved_tools.append(t)

        skills = data.get("skills", [])
        resolved_skills = []
        for s in skills:
            if hasattr(s, "to_dict"):
                resolved_skills.append(s)
            elif isinstance(s, dict):
                from tinycua_sdk.skills.models import Skill
                resolved_skills.append(Skill.from_dict(s))
            else:
                resolved_skills.append(s)

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            llm_model=llm_model,
            tools=resolved_tools,
            skills=resolved_skills,
            policy=AgentPolicy(**data.get("policy", {})) if data.get("policy") else None,
            metadata=data.get("metadata"),
            loop=data.get("loop"),
            tool_permissions=data.get("tool_permissions"),
            approval_workflow=data.get("approval_workflow"),
        )


__all__ = ["Agent"]
