"""End-to-end integration tests for full SDK workflow."""

import pytest
from tinycua_sdk import Agent, LanguageModel, tool


class TestEndToEnd:
    """Full workflow integration tests."""

    def test_agent_create_export_reload_roundtrip(self):
        """Create agent, export config, reload, verify equivalence."""
        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        agent = Agent(
            name="e2e-test",
            instructions="You are helpful.",
            llm_model=LanguageModel(model_name="gpt-4o"),
            tools=[add],
        )
        config = agent.to_config()
        restored = Agent.from_dict(config)
        assert restored.name == agent.name
        assert restored.instructions == agent.instructions

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_run_simple(self):
        """Run agent with simple prompt (skips if LLM unavailable via conftest)."""
        import os
        agent = Agent(
            name="hello-agent",
            instructions="You are helpful.",
            llm_model=LanguageModel(
                provider=os.environ.get("TINYCUA_PROVIDER", "openai-compatible"),
                model_name=os.environ.get("TINYCUA_MODEL", "qwen/qwen3.5-9b"),
                base_url=os.environ.get("TINYCUA_BASE_URL", "http://localhost:1234/v1"),
                api_key=os.environ.get("LLM_API_KEY", "dummy"),
            ),
        )
        response = await agent.run("Say 'hello' in one word.")
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_tool_invocation_via_executor(self):
        """Tool can be invoked directly through ToolExecutor."""
        from tinycua_sdk.agent.executor import ToolExecutor

        @tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        agent = Agent(llm_model=LanguageModel())
        result = await ToolExecutor.execute(greet, {"name": "World"}, agent)
        assert result == "Hello, World!"
