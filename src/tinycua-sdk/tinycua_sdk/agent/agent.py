"""Agent with lifecycle convenience wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.agent.backend_kind import BackendConfig

if TYPE_CHECKING:
    from tinycua_sdk.agent.config import AgentPolicy
    from tinycua_sdk.agent.loop import BaseLoop
    from tinycua_sdk.tools.decorators import Tool
    from tinycua_sdk.skills.models import Skill


# Parameters that were removed and should be rejected
_OBSOLETE_PARAMS = {
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
}


class Agent(AgentExecutor):
    """Stateless, fully runnable agent class.

    Inherits execution capabilities from AgentExecutor (which inherits from
    AgentDefinition).
    """

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
        max_depth: int = AgentExecutor.DEFAULT_MAX_DEPTH,
        loop: BaseLoop | None = None,
        strip_thinking: bool | list[str] | None = None,
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
            backend: Backend execution configuration.
            sub_agents: List of sub-agents for delegation.
            max_depth: Maximum delegation depth allowed.
            loop: Custom BaseLoop subclass instance.
            strip_thinking: Whether to strip thinking tags from responses.
            **kwargs: Rejects obsolete parameters for clear migration path.

        Raises:
            TypeError: If obsolete parameters are passed.

        """
        for key in kwargs:
            if key in _OBSOLETE_PARAMS:
                raise TypeError(
                    f"Agent() got an unexpected keyword argument '{key}'. "
                    f"This parameter has been removed. See migration guide."
                )

        super().__init__(
            name=name,
            instructions=instructions,
            llm_model=llm_model,
            tools=tools,
            skills=skills,
            policy=policy,
            backend=backend,
            sub_agents=sub_agents,
            max_depth=max_depth,
            loop=loop,
            strip_thinking=strip_thinking,
            **kwargs,
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
        llm_model = LLMModel.from_dict(llm_data) if isinstance(llm_data, dict) else LLMModel()

        backend_data = data.get("backend", {})
        backend = BackendConfig.from_dict(backend_data) if isinstance(backend_data, dict) else BackendConfig()

        tools = data.get("tools", [])
        from tinycua_sdk.tools.decorators import Tool
        resolved_tools = []
        for t in tools:
            if isinstance(t, Tool):
                resolved_tools.append(t)
            elif isinstance(t, dict):
                resolved_tools.append(Tool.from_config(t))
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

        loop_data = data.get("loop")
        loop = None
        if loop_data is not None:
            if isinstance(loop_data, dict):
                from tinycua_sdk.agent.loop import resolve_loop
                loop = resolve_loop(loop_data)
            else:
                loop = loop_data

        return cls(
            name=data.get("name", "assistant"),
            instructions=data.get("instructions", ""),
            llm_model=llm_model,
            tools=resolved_tools,
            skills=resolved_skills,
            backend=backend,
            sub_agents=data.get("sub_agents", []),
            max_depth=data.get("max_depth", cls.DEFAULT_MAX_DEPTH),
            strip_thinking=data.get("strip_thinking"),
            loop=loop,
        )

    @classmethod
    def from_template(
        cls, template_name: str, overrides: dict | None = None, **kwargs
    ) -> Agent:
        """Create an agent from a pre-built template.

        Args:
            template_name: Name of template to use ("coder", "researcher", "assistant")
            overrides: Optional dictionary of values to override in template
            **kwargs: Additional arguments to pass to Agent constructor

        Returns:
            Agent instance configured from template

        Raises:
            ValueError: If template name is not found or override keys are invalid

        Example:
            # Create coder agent
            agent = Agent.from_template("coder")

            # Customize template
            agent = Agent.from_template("coder", overrides={"model": "gpt-4o"})

            # Add additional configuration
            agent = Agent.from_template("coder", api_key="...")
        """
        from tinycua_sdk.agent.templates import (
            get_template,
            apply_template_overrides,
        )
        from tinycua_sdk.agent.config import AgentPolicy
        from tinycua_sdk.agent.loop import resolve_loop

        # Get base template
        template = get_template(template_name)

        # Apply overrides (with validation)
        if overrides:
            template = apply_template_overrides(template, overrides)

        # Extract config fields
        name = template.pop("name", template_name)
        system_prompt = template.pop("system_prompt", "")
        instructions = template.pop("instructions", "")
        model = template.pop("model", "gpt-4o-mini")
        provider = template.pop("provider", "openai-compatible")
        base_url = template.pop("base_url", None)
        api_key = template.pop("api_key", None)
        tool_names = template.pop("tools", [])
        skills = template.pop("skills", [])
        loop_config = template.pop("loop", "default")
        policy_data = template.pop("policy", {})
        keywords = template.pop("keywords", [])
        strip_thinking = template.pop("strip_thinking", None)

        # Override with kwargs if provided
        api_key = kwargs.pop("api_key", api_key)
        base_url = kwargs.pop("base_url", base_url)

        # Handle policy
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
            temperature=policy_data.get("temperature", 1.0),
        )

        # Build LLMModel from template fields
        llm_model = LLMModel(
            provider=provider,
            model_name=model,
            base_url=base_url,
            api_key=api_key or "",
            system_prompt=system_prompt,
        )

        # Resolve loop
        if isinstance(loop_config, str):
            if loop_config.lower() == "default":
                loop = resolve_loop(None)
            else:
                loop = resolve_loop({"max_iterations": 5})
        elif isinstance(loop_config, dict):
            loop = resolve_loop(loop_config)
        else:
            loop = resolve_loop(None)

        # Tools from templates cannot be resolved without a global registry.
        tools = []

        # Merge any remaining template fields into kwargs (filter out description)
        kwargs.pop("api_key", None)
        kwargs.pop("base_url", None)

        for key, value in template.items():
            if key not in kwargs and key != "description":
                kwargs[key] = value

        # Create and return agent with all config parameters
        return cls(
            name=name,
            instructions=instructions,
            llm_model=llm_model,
            tools=tools,
            policy=policy,
            strip_thinking=strip_thinking,
            loop=loop,
            skills=skills,
            **kwargs,
        )


__all__ = ["Agent"]
