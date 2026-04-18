"""Integration Tests: Agent Streaming

Tests based on example: 02_agent_streaming.py
Tests:
1. Text-only streaming
2. Streaming with tool calls
3. Streaming with multiple tool calls
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
def streaming_agent():
    """Create an agent with tools for streaming tests."""
    @tool()
    def get_weather(location: str) -> dict:
        """Get current weather for a location."""
        weather_db = {
            "tokyo": {"weather": "sunny", "temp": 22, "humidity": 65},
            "new york": {"weather": "cloudy", "temp": 18, "humidity": 72},
            "london": {"weather": "rainy", "temp": 12, "humidity": 85},
        }
        location_lower = location.lower()
        if location_lower in weather_db:
            return weather_db[location_lower]
        return {
            "weather": "unknown",
            "temp": 0,
            "humidity": 0,
            "note": f"No data for {location}",
        }

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
        name="streaming-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[get_weather, calculator],
    )


# =============================================================================
# Test Cases
# =============================================================================

class TestTextStreaming:
    """Test text-only streaming."""

    @pytest.mark.asyncio
    async def test_text_only_streaming(self, streaming_agent):
        """Test text-only streaming."""
        logger.info("Testing text-only streaming")
        chunks = []
        async for event in streaming_agent.stream("Say hello in 2 words"):
            if event.type == StreamEventType.CONTENT:
                content = event.data.get("content", "")
                if content:
                    chunks.append(content)
                    logger.debug(f"Chunk: {content[:50]}...")
        logger.info(f"Received {len(chunks)} content chunks")
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_text_only_streaming_done_event(self, streaming_agent):
        """Test that DONE event is received."""
        logger.info("Testing DONE event received")
        done_received = False
        async for event in streaming_agent.stream("Say hello in 2 words"):
            if event.type == StreamEventType.DONE:
                done_received = True
                logger.info(f"DONE event received: {event.data.get('finish_reason')}")
                break
        assert done_received is True


class TestToolStreaming:
    """Test streaming with tool calls."""

    @pytest.mark.asyncio
    async def test_stream_with_single_tool(self, streaming_agent):
        """Test streaming with single tool call."""
        logger.info("Testing streaming with single tool call")
        tool_calls_detected = []
        tool_results = []

        async for event in streaming_agent.stream("What's the weather in Tokyo?"):
            if event.type == StreamEventType.TOOL_CALL_START:
                tool_name = event.data.get("tool_name")
                tool_calls_detected.append(tool_name)
                logger.info(f"Tool call started: {tool_name}")
            elif event.type == StreamEventType.TOOL_RESULT_CHUNK:
                content = event.data.get("content", "")
                if content:
                    tool_results.append(content)
                    logger.debug(f"Tool result chunk: {content[:50]}...")

        logger.info(f"Tool calls: {len(tool_calls_detected)}, results: {len(tool_results)}")
        assert len(tool_calls_detected) > 0 or len(tool_results) > 0

    @pytest.mark.asyncio
    async def test_stream_with_tool_done_event(self, streaming_agent):
        """Test that tool DONE event is received."""
        logger.info("Testing tool DONE event")
        tool_done_received = False
        async for event in streaming_agent.stream("What's the weather in Tokyo?"):
            if event.type == StreamEventType.TOOL_RESULT_END:
                tool_done_received = True
                logger.info(f"Tool {event.data.get('tool_name')} completed")
                break
        assert tool_done_received is True


class TestMultipleToolsStreaming:
    """Test streaming with multiple tool calls."""

    @pytest.mark.asyncio
    async def test_stream_multiple_tools(self, streaming_agent):
        """Test streaming with multiple tool calls."""
        logger.info("Testing streaming with multiple tool calls")
        tool_calls_detected = []

        async for event in streaming_agent.stream("What is 5 + 3? What about 10 * 6?"):
            if event.type == StreamEventType.TOOL_CALL_START:
                tool_name = event.data.get("tool_name")
                tool_calls_detected.append(tool_name)
                logger.info(f"Tool called: {tool_name}")

        logger.info(f"Total tool calls: {len(tool_calls_detected)}")
        assert len(tool_calls_detected) > 0

    @pytest.mark.asyncio
    async def test_stream_multiple_tools_done(self, streaming_agent):
        """Test that DONE event is received after multiple tools."""
        logger.info("Testing DONE event after multiple tools")
        done_received = False
        async for event in streaming_agent.stream("What is 5 + 3? What about 10 * 6?"):
            if event.type == StreamEventType.DONE:
                done_received = True
                logger.info(f"Stream done: {event.data.get('finish_reason')}")
                break
        assert done_received is True


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
