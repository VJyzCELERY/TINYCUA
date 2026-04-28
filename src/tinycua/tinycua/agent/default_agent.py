"""Default agent factory for TinyCUA.

Creates a pre-configured agent that works out of the box with an OpenAI-compatible endpoint.
"""

from __future__ import annotations

from tinycua.constants import DEFAULT_SYSTEM_PROMPT
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.core.config import SDKConfig
    from tinycua_sdk.tools.decorators import Tool


def create_default_agent(
    config: SDKConfig | None = None,
    tools: list[Tool] | None = None,
) -> Agent:
    """Create a default agent configured for an OpenAI-compatible endpoint.

    Args:
        config: Optional user config. If None, loads from UserConfig.
        tools: Optional list of tools. If None, includes memory and
            context tools.

    Returns:
        Agent instance configured for local OpenAI-compatible execution.
    """
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.agent.config import AgentPolicy

    if config is None:
        try:
            from tinycua.config.user_config import UserConfig

            config = UserConfig.load()
        except (OSError, ValueError, ImportError):
            from tinycua_sdk.core.config import SDKConfig

            config = SDKConfig()

    # Default tools: memory + context tools
    if tools is None:
        from tinycua.agent.tools.context_tools import (
            get_context_summary_tool,
            get_recent_turns_tool,
            search_context_grep_tool,
        )
        from tinycua.agent.tools.memory_tools import (
            clear_memory,
            forget,
            list_memory,
            recall,
            remember,
        )

        tools = [
            remember,
            recall,
            forget,
            list_memory,
            clear_memory,
            search_context_grep_tool,
            get_context_summary_tool,
            get_recent_turns_tool,
        ]

    policy = AgentPolicy(max_tool_calls=10, parallel_tool_calls=True)

    agent = Agent(
        name="assistant",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model=config.llm.model,
        provider=config.llm.provider,
        base_url=config.llm.base_url,
        api_key=config.llm.api_key.get_secret_value() if config.llm.api_key else None,
        tools=tools,
        policy=policy,
        mode="local",
    )

    return agent
