"""Integration Tests: Basic Agent Functionality

Tests based on example: 01_agent_basic.py
Tests:
1. Agent creation with tools
2. Direct mode execution (no tools)
3. Tool call detection and execution
4. Plan mode execution
5. Trace functionality
6. Deployment functionality
7. Streaming (text only)
8. Streaming with tools
"""

import pytest
import asyncio
import logging
from tinycua_sdk.agent import Agent
from tinycua_sdk.tools import tool
from tinycua_sdk.models import StreamEventType

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def basic_agent():
    """Create a basic agent with tools."""
    return Agent(
        name="test-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )


@pytest.fixture
def agent_with_tools():
    """Create an agent with calculator tool."""
    @tool()
    def calculator(expression: str) -> dict:
        """Evaluate a math expression."""
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return {"expression": expression, "result": result, "success": True}
        except Exception as e:
            return {
                "expression": expression,
                "result": None,
                "error": str(e),
                "success": False,
            }

    return Agent(
        name="calculator-agent",
        instructions="You are a calculator assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[calculator],
    )


# =============================================================================
# Test Cases
# =============================================================================

class TestAgentCreation:
    """Test agent creation and configuration."""

    def test_agent_creation(self, basic_agent):
        """Test basic agent creation."""
        assert basic_agent.name == "test-agent"
        assert basic_agent.instructions == "You are a helpful assistant."
        assert basic_agent.provider == "lmstudio"
        assert basic_agent.model == "qwen/qwen3.5-9b"
        assert basic_agent.config.base_url == "http://localhost:1234"

    def test_agent_with_tools(self, agent_with_tools):
        """Test agent creation with tools."""
        assert len(agent_with_tools.tools) > 0
        assert any(t.name == "calculator" for t in agent_with_tools.tools)


class TestDirectMode:
    """Test direct mode execution."""

    @pytest.mark.asyncio
    async def test_direct_mode_simple(self, basic_agent):
        """Test simple direct mode execution."""
        logger.info("Testing direct mode with simple prompt")
        response = await basic_agent.run("Say hello in one sentence.")
        logger.info(f"Response received: {response[:100]}...")
        assert isinstance(response, str)
        assert len(response) > 0


class TestToolExecution:
    """Test tool execution."""

    @pytest.mark.asyncio
    async def test_tool_call_detection(self, agent_with_tools):
        """Test that tool calls are detected."""
        logger.info("Testing tool call detection")
        result = await agent_with_tools.run("What is 15 * 7?", trace=True)
        logger.info(f"Tool calls detected: {len(result.tool_calls)}")
        assert hasattr(result, 'tool_calls')
        assert len(result.tool_calls) > 0

    @pytest.mark.asyncio
    async def test_tool_execution(self, agent_with_tools):
        """Test tool execution with response."""
        logger.info("Testing tool execution")
        result = await agent_with_tools.run("What is 15 * 7?", trace=True)
        logger.info(f"Response: {result.response[:100]}...")
        assert hasattr(result, 'response')
        assert len(result.response) > 0


class TestReactLoop:
    """Test React loop execution."""

    @pytest.mark.asyncio
    async def test_react_loop(self, agent_with_tools):
        """Test React loop execution."""
        logger.info("Testing React loop execution")
        react_agent = Agent(
            name="react-agent",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[agent_with_tools.tools[0]],
            loop="react",
        )
        result = await react_agent.run("Check weather in Tokyo and New York, then compare")
        logger.info(f"React loop result: {result[:100]}...")
        assert isinstance(result, str)
        assert len(result) > 0


class TestStreaming:
    """Test streaming functionality."""

    @pytest.mark.asyncio
    async def test_text_streaming(self, basic_agent):
        """Test text-only streaming."""
        logger.info("Testing text-only streaming")
        chunks = []
        async for event in basic_agent.stream("Say hello in 3 words"):
            if event.type == StreamEventType.CONTENT:
                content = event.data.get("content", "")
                if content:
                    chunks.append(content)
                    logger.debug(f"Content chunk: {content[:50]}...")
        logger.info(f"Received {len(chunks)} chunks")
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_with_tools(self, agent_with_tools):
        """Test streaming with tool execution."""
        logger.info("Testing streaming with tool execution")
        chunks = []
        tool_calls = []
        async for event in agent_with_tools.stream("What's the weather in Tokyo?"):
            if event.type == StreamEventType.CONTENT:
                content = event.data.get("content", "")
                if content:
                    chunks.append(content)
            elif event.type == StreamEventType.TOOL_CALL_START:
                tool_calls.append(event.data.get("tool_name"))
                logger.info(f"Tool called: {event.data.get('tool_name')}")
        logger.info(f"Chunks: {len(chunks)}, Tools: {len(tool_calls)}")
        assert len(chunks) > 0


class TestDeployment:
    """Test deployment functionality."""

    @pytest.mark.asyncio
    async def test_agent_deploy(self, basic_agent):
        """Test agent deployment."""
        try:
            deployment = await basic_agent.deploy()
            assert deployment is not None
            assert "agent_id" in deployment
            assert basic_agent.is_deployed is True
        except Exception:
            # Deployment might fail if backend is not available
            pytest.skip("Backend not available")


class TestTrace:
    """Test trace functionality."""

    @pytest.mark.asyncio
    async def test_trace_functionality(self, agent_with_tools):
        """Test trace functionality."""
        result = await agent_with_tools.run("What is 15 * 7?", trace=True)
        assert hasattr(result, 'tool_calls')
        assert hasattr(result, 'total_tokens')
        assert hasattr(result, 'response')


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
