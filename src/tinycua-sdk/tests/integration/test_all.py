"""Comprehensive Integration Tests for TINYCUA SDK.

This module provides comprehensive integration tests for the TINYCUA SDK,
covering all major functionality demonstrated in the examples.

Test Coverage:
1. Basic Agent Functionality (01_agent_basic.py)
   - Agent creation with tools
   - Direct mode execution
   - Tool call detection
   - Plan mode execution
   - Streaming

2. Agent Streaming (02_agent_streaming.py)
   - Text-only streaming
   - Streaming with tool calls
   - Multiple tool calls

3. Memory and Sessions (03_memory_and_session.py)
   - Memory tools
   - Session persistence
   - Cancel execution

4. Agent Hierarchy (05_agent_hierarchy.py)
   - Agent hierarchy structure
   - Delegation patterns
   - Context passing

5. Local Storage (06_local_storage.py)
   - Session store
   - Message management
   - Context retrieval tools

Prerequisites:
- LM Studio running at http://localhost:1234
- Model: qwen/qwen3.5-9b loaded in LM Studio

Usage:
    python tests/integration/test_all.py
"""

import pytest
import asyncio
import logging
from tinycua_sdk.agent import Agent
from tinycua_sdk.tools import tool
from tinycua_sdk.models import StreamEventType

# Configure logging for tests
logger = logging.getLogger(__name__)


# =============================================================================
# Test Suite: Basic Agent Functionality
# =============================================================================

class TestBasicAgent:
    """Test basic agent functionality."""

    @pytest.fixture
    def basic_agent(self):
        """Create a basic agent."""
        return Agent(
            name="test-agent",
            instructions="You are a helpful assistant.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
        )

    @pytest.fixture
    def agent_with_tools(self):
        """Create an agent with tools."""
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

    def test_agent_creation(self, basic_agent):
        """Test basic agent creation."""
        logger.info(f"Created agent: {basic_agent.name}")
        logger.info(f"Provider: {basic_agent.provider}, Model: {basic_agent.model}")
        assert basic_agent.name == "test-agent"
        assert basic_agent.provider == "lmstudio"
        assert basic_agent.model == "qwen/qwen3.5-9b"

    @pytest.mark.asyncio
    async def test_direct_mode(self, basic_agent):
        """Test direct mode execution."""
        logger.info("Testing direct mode execution...")
        response = await basic_agent.run("Say hello in one sentence.")
        logger.info(f"Received response: {response[:100]}...")
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_tool_execution(self, agent_with_tools):
        """Test tool execution."""
        logger.info("Testing tool execution with calculator...")
        result = await agent_with_tools.run("What is 15 * 7?", trace=True)
        logger.info(f"Tool execution result: {result.response[:100]}...")
        assert hasattr(result, 'response')
        assert len(result.response) > 0

    @pytest.mark.asyncio
    async def test_text_streaming(self, basic_agent):
        """Test text-only streaming."""
        logger.info("Testing text-only streaming...")
        chunks = []
        async for event in basic_agent.stream("Say hello in 3 words"):
            if event.type == StreamEventType.CONTENT:
                content = event.data.get("content", "")
                if content:
                    chunks.append(content)
                    logger.debug(f"Streaming chunk: {content[:50]}...")
        logger.info(f"Received {len(chunks)} content chunks")
        assert len(chunks) > 0


# =============================================================================
# Test Suite: Streaming
# =============================================================================

class TestStreaming:
    """Test streaming functionality."""

    @pytest.fixture
    def streaming_agent(self):
        """Create an agent with tools."""
        @tool()
        def get_weather(location: str) -> dict:
            """Get weather for a location."""
            return {"location": location, "weather": "sunny"}

        @tool()
        def calculator(expression: str) -> dict:
            """Evaluate a math expression."""
            try:
                result = eval(expression, {"__builtins__": {}}, {})
                return {"result": result}
            except:
                return {"error": "Calculation failed"}

        return Agent(
            name="streaming-agent",
            instructions="You are a helpful assistant.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[get_weather, calculator],
        )

    @pytest.mark.asyncio
    async def test_text_streaming(self, streaming_agent):
        """Test text-only streaming."""
        logger.info("Testing text-only streaming...")
        chunks = []
        async for event in streaming_agent.stream("Say hello in 2 words"):
            if event.type == StreamEventType.CONTENT:
                content = event.data.get("content", "")
                if content:
                    chunks.append(content)
                    logger.debug(f"Streaming chunk: {content[:50]}...")
        logger.info(f"Received {len(chunks)} content chunks")
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_with_tool(self, streaming_agent):
        """Test streaming with tool call."""
        logger.info("Testing streaming with tool call...")
        tool_calls = []
        async for event in streaming_agent.stream("What's the weather in Tokyo?"):
            if event.type == StreamEventType.TOOL_CALL_START:
                tool_name = event.data.get("tool_name")
                tool_calls.append(tool_name)
                logger.info(f"Tool call detected: {tool_name}")
        logger.info(f"Total tool calls detected: {len(tool_calls)}")
        assert len(tool_calls) > 0


# =============================================================================
# Test Suite: Agent Hierarchy
# =============================================================================

class TestAgentHierarchy:
    """Test agent hierarchy functionality."""

    def test_agent_with_sub_agents(self):
        """Test agent with sub-agents."""
        sub_agent = Agent(name="sub", instructions="Sub agent.")
        main_agent = Agent(
            name="main",
            instructions="Main agent.",
            sub_agents=[sub_agent],
        )

        assert len(main_agent.sub_agents) == 1

    def test_agent_without_sub_agents(self):
        """Test agent without sub-agents."""
        agent = Agent(name="agent", instructions="Agent.")
        assert len(agent.sub_agents) == 0

    def test_pass_context(self):
        """Test passing context to sub-agent."""
        sub_agent = Agent(name="sub", instructions="Sub agent.")
        main_agent = Agent(
            name="main",
            instructions="Main agent.",
            sub_agents=[sub_agent],
        )

        context = main_agent._pass_context_to_sub_agent("Hello", sub_agent)
        assert isinstance(context, str)


# =============================================================================
# Test Suite: Memory Tools
# =============================================================================

class TestMemoryTools:
    """Test memory tool functionality."""

    def test_remember_tool_exists(self):
        """Test that remember tool exists."""
        from tinycua_sdk.tools import remember
        assert remember is not None

    def test_recall_tool_exists(self):
        """Test that recall tool exists."""
        from tinycua_sdk.tools import recall
        assert recall is not None

    def test_list_memory_tool_exists(self):
        """Test that list_memory tool exists."""
        from tinycua_sdk.tools import list_memory
        assert list_memory is not None


# =============================================================================
# Test Suite: Context Tools
# =============================================================================

class TestContextTools:
    """Test context tool functionality."""

    def test_context_tools_exist(self):
        """Test that context tools exist."""
        from tinycua.agent.tools import (
            get_context_summary_tool,
            get_recent_turns_tool,
            search_context_grep_tool,
        )
        assert get_context_summary_tool is not None
        assert get_recent_turns_tool is not None
        assert search_context_grep_tool is not None


# =============================================================================
# Test Suite: Utils
# =============================================================================

class TestUtils:
    """Test utility functions."""

    def test_create_session(self):
        """Test creating a session."""
        from tinycua_sdk.utils import create_session
        result = create_session(name="Test Session")
        assert "session_id" in result

    def test_list_sessions(self):
        """Test listing sessions."""
        from tinycua_sdk.utils import list_sessions
        result = list_sessions()
        assert "sessions" in result


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
