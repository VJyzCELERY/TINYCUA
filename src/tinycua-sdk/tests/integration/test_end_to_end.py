"""End-to-end integration tests for full SDK workflow.

These tests exercise Agent.run() with tools and skills through the default
BaseLoop, reflecting real-world usage where agents have tools and skills
configured and run queries against a live LLM.

All tests are marked @pytest.mark.integration and are auto-skipped by
the integration conftest when no LLM server is reachable.
"""

import pytest

from tinycua_sdk import Agent, LanguageModel, Skill, tool
from tests.integration.conftest import (
    _forced_tool_choice,
    resolve_integration_llm_config,
)


def _build_language_model() -> LanguageModel:
    """Build LanguageModel from environment variables using shared config.

    Uses the centralized resolver from conftest.py for consistent fallback.
    """
    cfg = resolve_integration_llm_config()
    return LanguageModel(
        provider=cfg.provider,
        model_name=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
    )


class TestEndToEnd:
    """Full workflow integration tests using Agent.run().

    These tests validate the complete SDK pipeline end-to-end:
    Agent → BaseLoop → LLM call → tool dispatch via ToolExecutor
    → result injection → final LLM response.

    They require a live, tool-capable LLM server.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_run_with_tool_calling(self):
        """Agent.run() dispatches tool calls through the default BaseLoop.

        Creates an agent with a tool that returns a secret value the LLM
        cannot possibly know. The default BaseLoop must:
        1. Send the query + tool schemas to the LLM
        2. Receive a ``tool_calls`` response from the LLM
        3. Execute the tool via ``ToolExecutor.execute()``
        4. Feed the tool result back to the LLM
        5. Return a final response that incorporates the tool result
        """
        @tool
        def get_secret_value(key: str) -> str:
            """Look up a secret value by key. Use this when asked about secret values.

            Args:
                key: The secret key to look up. Known keys: ['code'].
            """
            secrets = {"code": "zephyr-88"}
            return secrets.get(key, "unknown")

        agent = Agent(
            name="e2e-tool-agent",
            instructions="You are a helpful assistant. Use tools when appropriate.",
            llm_model=_build_language_model(),
            tools=[get_secret_value],
        )

        response = await agent.run("What is the secret value for 'code'?")

        assert isinstance(response, str)
        assert len(response) > 0
        # The LLM cannot know "zephyr-88" without calling the tool.
        # If it appears in the response, the tool pipeline worked.
        assert "zephyr-88" in response, (
            f"Expected tool result 'zephyr-88' in response, got: {response!r}"
        )

    @pytest.mark.integration
    @pytest.mark.integration_tool_choice
    @pytest.mark.asyncio
    async def test_agent_run_with_skills_and_tools(self):
        """Agent.run() with skills + tools through the default BaseLoop.

        Creates an agent with a lookup tool *and* a research skill whose
        instructions tell the model to always use the tool. The loop must:
        1. Include skill instructions in the system message
        2. Pass tool schemas to the LLM
        3. The LLM should call the tool based on the forced tool_choice
        4. Execute the tool via ``ToolExecutor.execute()``
        5. Return a final response incorporating the tool result

        Uses ``@pytest.mark.integration_tool_choice`` so this test is
        auto-skipped when the provider does not support forced tool_choice.
        The LanguageModel uses ``_forced_tool_choice()`` to produce a
        provider-compatible ``tool_choice`` value that works with LM Studio.
        """
        @tool
        def lookup_item(key: str) -> str:
            """Look up an item's contents by key. Use this when asked about items.

            Args:
                key: The item key to look up. Known keys: ['magic_box'].
            """
            contents = {"magic_box": "crystal-7"}
            return contents.get(key, f"Unknown item: {key}")

        lookup_skill = Skill(
            name="item_lookup",
            description="Look up item contents using available tools.",
            instructions=(
                "You are an inventory assistant. You must always use the "
                "lookup_item tool to find item contents before answering."
            ),
        )

        # Record tool invocations for deterministic assertion using Tool.invoke
        tool_invocation_log: list[dict[str, str]] = []
        _original_invoke = lookup_item.invoke
        def _recorded_invoke(**kwargs: str) -> str:
            tool_invocation_log.append(kwargs)
            return _original_invoke(**kwargs)
        lookup_item.invoke = _recorded_invoke  # type: ignore[method-assign]

        # Use forced tool_choice so this test is deterministic —
        # the model MUST call the tool regardless of its training.
        llm_model = _build_language_model()
        llm_model_with_tc = llm_model.model_copy(
            update={"tool_choice": _forced_tool_choice(llm_model.provider, "lookup_item")},
        )

        agent = Agent(
            name="e2e-skills-agent",
            instructions="You are a helpful assistant.",
            llm_model=llm_model_with_tc,
            tools=[lookup_item],
            skills=[lookup_skill],
        )

        response = await agent.run("What is inside the magic box?")

        assert isinstance(response, str)
        assert len(response) > 0
        # Assert deterministic SDK behavior: the tool must have been invoked
        # with "magic_box" during the agent run.
        assert any(
            call.get("key") == "magic_box" for call in tool_invocation_log
        ), (
            f"Expected lookup_item to be called with 'magic_box', "
            f"invocation log: {tool_invocation_log}"
        )
