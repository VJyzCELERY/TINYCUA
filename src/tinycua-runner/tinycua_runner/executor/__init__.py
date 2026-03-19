"""Executor for running agents with stateless execution."""

from __future__ import annotations

import logging
from typing import Any

from tinycua_runner.registry import get_registry

logger = logging.getLogger(__name__)


class Executor:
    """Handles agent execution with bundled tools."""

    def __init__(
        self,
        bundled_tools: list[dict[str, Any]] | None = None,
    ):
        """Initialize executor.

        Args:
            bundled_tools: Optional list of tool bundles from backend
        """
        self._register_tools(bundled_tools or [])

    def _register_tools(self, tools: list[dict[str, Any]]) -> None:
        """Register bundled tools to the registry.

        Args:
            tools: List of tool bundles
        """
        registry = get_registry()

        for tool_bundle in tools:
            registry.register(tool_bundle)

        logger.info(f"Registered {len(tools)} bundled tools")

    def get_tools(self) -> list[Any]:
        """Get all tools for agent execution.

        Returns:
            List of Tool objects
        """
        from tinycua_sdk.tools.decorators import Tool
        from tinycua_runner.registry import get_registry

        registry = get_registry()
        tools = []

        for tool_bundle in registry.list_all():
            materialized_fn = registry.get_materialized(tool_bundle["name"])
            if materialized_fn is None:
                logger.warning(f"Failed to materialize tool: {tool_bundle['name']}")
                continue

            tool = Tool(
                name=tool_bundle["name"],
                description=tool_bundle.get("description", ""),
                parameters=tool_bundle.get("parameters", {}),
                _source=tool_bundle.get("source", ""),
            )
            # Store the materialized function separately for invocation
            tool._fn = materialized_fn
            tools.append(tool)

        return tools

    def get_context_tools(self) -> list[Any]:
        """Get context tools with session store.

        Returns:
            List of context tool callables
        """
        # Skip context tools for now to test basic execution
        return []

    async def execute(
        self,
        agent_config: dict[str, Any],
        user_input: str,
    ):
        """Execute agent and yield events.

        Args:
            agent_config: Agent configuration
            user_input: User input

        Yields:
            SSE events
        """
        from tinycua_sdk.agent import Agent

        all_tools = []
        all_tools.extend(self.get_context_tools())
        all_tools.extend(self.get_tools())

        api_key = agent_config.get("api_key")
        provider = agent_config.get("provider", "openai")
        base_url = agent_config.get("base_url")

        logger.info(
            f"Agent config: provider={provider}, base_url={base_url}, model={agent_config.get('model')}"
        )

        if provider in ("lmstudio", "ollama") and not api_key:
            api_key = None

        agent = Agent(
            name=agent_config.get("name", "runner-agent"),
            instructions=agent_config.get("instructions", ""),
            system_prompt=agent_config.get(
                "system_prompt", "You are a helpful assistant."
            ),
            model=agent_config.get("model", "gpt-4o-mini"),
            provider=provider,
            base_url=agent_config.get("base_url"),
            api_key=api_key,
            tools=all_tools,
            mode="local",
        )

        logger.info(f"Running agent: {agent.name}, mode: {agent.config.mode}")

        try:
            result = await agent.run(user_input, stream_sse=True)
            logger.info(f"Result type: {type(result)}")

            async for event in result:
                logger.info(f"Yielding event: {type(event)}")
                yield event
        except Exception as e:
            import traceback

            logger.error(f"Error running agent: {e}")
            traceback.print_exc()
            yield f"data: {{'error': '{str(e)}'}}\n\n"
