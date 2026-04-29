"""Agent with backward-compatible lifecycle convenience wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.core.providers import DEFAULT_BASE_URL, OPENAI_COMPATIBLE
if TYPE_CHECKING:
    from tinycua_sdk.agent.config import AgentPolicy
    from tinycua_sdk.tools.decorators import Tool


class Agent(AgentExecutor):
    """Thin backward-compatible class that extends AgentExecutor.

    Inherits all configuration, properties, and execution capabilities from
    AgentExecutor (which inherits from AgentDefinition).
    """

    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        system_prompt: str = "You are a helpful assistant.",
        model: str = "gpt-4o-mini",
        provider: str = OPENAI_COMPATIBLE,
        base_url: str | None = DEFAULT_BASE_URL,
        api_key: str | None = None,
        tools: list[Tool] | None = None,
        policy: AgentPolicy | None = None,
        mode: str = "local",
        backend_url: str | None = None,
        backend_api_key: str | None = None,
        backend_headers: dict[str, str] | None = None,
        agent_id: str | None = None,
        runner: Any = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = AgentExecutor.DEFAULT_MAX_DEPTH,
        current_depth: int = 0,
        keywords: list[str] | None = None,
        strip_thinking: bool | list[str] | None = None,
        loop: Any = None,
        skills: list[str] | None = None,
    ):
        """Initialize the Agent.

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
            runner: Optional runner instance for remote execution.
            sub_agents: List of sub-agents for delegation.
            max_depth: Maximum delegation depth allowed.
            current_depth: Current delegation depth (internal).
            keywords: Keywords for task routing to this agent.
            strip_thinking: Whether to strip thinking tags from responses.
            loop: Custom BaseLoop subclass instance.
            skills: List of skill names to load for the agent.

        """
        super().__init__(
            name=name,
            instructions=instructions,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            tools=tools,
            policy=policy,
            mode=mode,
            backend_url=backend_url,
            backend_api_key=backend_api_key,
            backend_headers=backend_headers,
            agent_id=agent_id,
            sub_agents=sub_agents,
            max_depth=max_depth,
            current_depth=current_depth,
            keywords=keywords,
            strip_thinking=strip_thinking,
            loop=loop,
            skills=skills,
        )
        self.runner = runner

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
        provider = template.pop("provider", OPENAI_COMPATIBLE)
        base_url = template.pop("base_url", DEFAULT_BASE_URL)
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

        # Resolve loop string to loop instance
        loop = resolve_loop(loop_config)

        # Tool names from templates cannot be resolved without a global registry.
        # Tools must be passed explicitly via the tools parameter or add_tools().
        tools = []

        # Merge any remaining template fields into kwargs (filter out description)
        # Also handle api_key conflict - pop from kwargs if already passing separately
        kwargs.pop("api_key", None)
        kwargs.pop("base_url", None)

        for key, value in template.items():
            if key not in kwargs and key != "description":
                kwargs[key] = value

        # Create and return agent with all config parameters
        return cls(
            name=name,
            instructions=instructions,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            tools=tools,
            policy=policy,
            strip_thinking=strip_thinking,
            loop=loop,
            keywords=keywords,
            skills=skills,
            **kwargs,
        )


__all__ = ["Agent"]
