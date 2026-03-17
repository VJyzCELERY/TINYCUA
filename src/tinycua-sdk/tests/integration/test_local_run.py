"""End-to-end integration tests for local agent execution.

These tests require:
- LM Studio running with qwen/qwen3.5-9b model loaded
- LM Studio API accessible at http://localhost:1234/v1

Run with: pytest tests/integration/test_local_run.py -v -m lm_studio
"""

import pytest


class TestLocalAgentRun:
    """Test agent.run() with local LLM."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_run_simple_text(self):
        """Test simple text completion without tools."""
        from tinycua_sdk.models import Agent

        agent = Agent(
            name="test-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
        )

        response = await agent.run("Say 'hello' in one word")
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_run_with_tool(self):
        """Test agent with tool calling."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.models import Agent

        @tool()
        def get_weather(location: str) -> dict:
            """Get weather for a location."""
            return {"weather": "sunny", "temp": 22}

        agent = Agent(
            name="test-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[get_weather],
        )

        response = await agent.run("What's the weather in Tokyo?")
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_run_with_trace(self):
        """Test agent with trace enabled."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.models import Agent

        @tool()
        def calculator(expression: str) -> dict:
            """Evaluate math expression."""
            try:
                result = eval(expression, {"__builtins__": {}}, {})
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}

        agent = Agent(
            name="test-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[calculator],
        )

        result = await agent.run("What is 5 + 3?", trace=True)
        assert hasattr(result, "response")
        assert hasattr(result, "tool_calls")
        assert len(result.tool_calls) > 0


class TestLocalAgentStream:
    """Test agent.stream() with local LLM."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stream_text_only(self):
        """Test streaming text without tools."""
        from tinycua_sdk.models import Agent, StreamEventType

        agent = Agent(
            name="test-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
        )

        events = []
        async for event in agent.stream("Say 'hi' in one word"):
            events.append(event)

        content_events = [e for e in events if e.type == StreamEventType.CONTENT]
        assert len(content_events) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stream_with_tool(self):
        """Test streaming with tool execution."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.models import Agent, StreamEventType

        @tool()
        def get_weather(location: str) -> dict:
            """Get weather for a location."""
            return {"weather": "sunny", "temp": 22}

        agent = Agent(
            name="test-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[get_weather],
        )

        events = []
        async for event in agent.stream("What's the weather in Tokyo?"):
            events.append(event)

        tool_call_events = [
            e for e in events if e.type == StreamEventType.TOOL_CALL_END
        ]
        tool_result_events = [
            e for e in events if e.type == StreamEventType.TOOL_RESULT_END
        ]

        assert len(tool_call_events) > 0 or len(tool_result_events) > 0


class TestPlanMode:
    """Test plan mode execution."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_plan_mode(self):
        """Test agent in plan mode."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.models import Agent

        @tool()
        def get_weather(location: str) -> dict:
            """Get weather for a location."""
            return {"weather": "sunny", "temp": 22}

        @tool()
        def calculator(expression: str) -> dict:
            """Evaluate math expression."""
            try:
                result = eval(expression, {"__builtins__": {}}, {})
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}

        agent = Agent(
            name="planner-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[get_weather, calculator],
            plan_mode="plan",
        )

        response = await agent.run("Check weather in Tokyo and calculate 2+2")
        assert isinstance(response, str)
        assert len(response) > 0


class TestDeployMode:
    """Test agent deploy functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_deploy(self):
        """Test agent deploy."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.models import Agent

        @tool()
        def dummy_tool() -> str:
            """A dummy tool."""
            return "result"

        agent = Agent(
            name="test-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[dummy_tool],
        )

        result = await agent.deploy()
        assert result["status"] == "deployed"
        assert "agent_id" in result
        assert agent.is_deployed


class TestRunner:
    """Test Runner class directly."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_runner_direct(self):
        """Test Runner class directly."""
        from tinycua_sdk.runner import Runner
        from tinycua_sdk.models import AgentConfig
        from tinycua_sdk.tools import tool

        @tool()
        def hello() -> str:
            """Say hello."""
            return "Hello!"

        config = AgentConfig(
            name="test",
            model="qwen/qwen3.5-9b",
            provider="lmstudio",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[hello],
        )

        runner = Runner(config)
        response = await runner.chat("Say hello")
        assert isinstance(response, str)
        await runner.close()
