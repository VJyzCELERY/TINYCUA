"""End-to-end integration tests for full SDK workflow.

These tests exercise Agent.run() with tools and skills through the default
BaseLoop, reflecting real-world usage where agents have tools and skills
configured and run queries against a live LLM.

All tests are marked @pytest.mark.integration and are auto-skipped by
the integration conftest when no LLM server is reachable.
"""

import os
import pytest

from tinycua_sdk import Agent, LanguageModel, Skill, tool


def _build_language_model() -> LanguageModel:
    """Build LanguageModel from environment variables.

    Uses TINYCUA_* or LLM_* env vars, falling back to localhost defaults.
    """
    return LanguageModel(
        provider=os.environ.get("TINYCUA_PROVIDER", "openai-compatible"),
        model_name=os.environ.get(
            "TINYCUA_MODEL",
            os.environ.get("LLM_MODEL", "qwen/qwen3.5-9b"),
        ),
        base_url=os.environ.get(
            "TINYCUA_BASE_URL",
            os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        ),
        api_key=os.environ.get(
            "TINYCUA_API_KEY",
            os.environ.get("LLM_API_KEY", "dummy"),
        ),
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
    @pytest.mark.asyncio
    async def test_agent_run_with_skills_and_tools(self):
        """Agent.run() with skills + tools through the default BaseLoop.

        Creates an agent with a lookup tool *and* a research skill whose
        instructions tell the model to always use the tool. The loop must:
        1. Include skill instructions in the system message
        2. Pass tool schemas to the LLM
        3. The LLM should call the tool based on the skill instructions
        4. Execute the tool via ``ToolExecutor.execute()``
        5. Return a final response incorporating the tool result
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

        agent = Agent(
            name="e2e-skills-agent",
            instructions="You are a helpful assistant.",
            llm_model=_build_language_model(),
            tools=[lookup_item],
            skills=[lookup_skill],
        )

        response = await agent.run("What is inside the magic box?")

        assert isinstance(response, str)
        assert len(response) > 0
        # The LLM cannot know "crystal-7" without calling the tool.
        # If it appears in the response, the skill + tool pipeline worked.
        assert "crystal-7" in response, (
            f"Expected tool result 'crystal-7' in response, got: {response!r}"
        )
