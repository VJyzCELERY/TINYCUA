"""Agent with lifecycle convenience wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_model import LanguageModel

if TYPE_CHECKING:
    from tinycua_sdk.agent.config import AgentPolicy
    from tinycua_sdk.agent.loop import BaseLoop
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.skills.models import Skill


class Agent(AgentExecutor):
    """Stateless, fully runnable agent class.

    Inherits execution capabilities from AgentExecutor (which inherits from
    AgentDefinition).
    """

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
            **kwargs: Additional keyword arguments (unused).

        Raises:
            TypeError: If unknown parameters are passed.

        """
        if kwargs:
            raise TypeError(
                f"Agent() got unexpected keyword argument(s): {', '.join(sorted(kwargs.keys()))}"
            )

        super().__init__(
            name=name,
            instructions=instructions,
            llm_model=llm_model,
            tools=tools,
            skills=skills,
            policy=policy,
            loop=loop,
        )

    def add_tools(self, tool_or_list: Tool | list[Tool]) -> None:
        """Append one or more tools to the agent.

        Args:
            tool_or_list: A single Tool or a list of Tools.
        """
        if isinstance(tool_or_list, list):
            self.config.tools.extend(tool_or_list)
        else:
            self.config.tools.append(tool_or_list)

    def add_skills(self, skill_or_list: Any | list[Any]) -> None:
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
    def from_config(cls, config: str | Any) -> Agent:
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

        policy_data = data.get("policy", {})
        from tinycua_sdk.agent.config import AgentPolicy
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
        )

        metadata = data.get("metadata", {})

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            llm_model=llm_model,
            tools=resolved_tools,
            skills=resolved_skills,
            policy=policy,
            metadata=metadata if metadata else None,
            loop=data.get("loop"),
        )


__all__ = ["Agent"]
