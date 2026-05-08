"""Integration tests for Stage 5 — Streaming.

Tests streaming with stream=True (raw SSE passthrough) and stream=False
(string return), mocking the LLM call at the agent level.
"""

from __future__ import annotations

import pytest

from tinycua_sdk import Agent, LanguageModel, tool


class TestStreamingOff:
    """Test stream=False returns a plain string."""

    @pytest.mark.asyncio
    async def test_off_returns_string(self):
        """Default mode returns str."""
        agent = Agent(llm_model=LanguageModel())

        async def mock_call(messages, tools, stream=False):
            return {
                "content": "Hello!",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call

        result = await agent.run("Say hello", stream=False)
        assert isinstance(result, str)
        assert len(result) > 0


class TestStreamingOn:
    """Test stream=True yields raw SSE events."""

    @pytest.mark.asyncio
    async def test_stream_yields_raw_events(self):
        """stream=True yields raw events including deltas."""
        agent = Agent(llm_model=LanguageModel())

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_text.delta",
                    "delta": "Hello",
                    "item_id": "1",
                }

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("Say hello", stream=True)
        events = [e async for e in stream_iter]

        delta_events = [e for e in events if e["type"] == "response.output_text.delta"]
        assert len(delta_events) > 0
        assert any(e["type"] == "response.created" for e in events)
        assert any(e["type"] == "response.completed" for e in events)


class TestStreamingWithToolCalls:
    """Test streaming with tool calls."""

    @pytest.mark.asyncio
    async def test_stream_tool_calls(self):
        """Tool call events pass through in stream."""

        @tool
        def get_time() -> str:
            """Get the current time."""
            return "12:00"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        call_count = 0

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.tool_call.delta",
                        "index": 0,
                        "id": "call_1",
                        "name": "get_time",
                        "arguments": "{}",
                    }
                else:
                    yield {
                        "type": "response.output_text.delta",
                        "delta": "The time is 12:00.",
                        "item_id": "2",
                    }

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("What time?", stream=True)
        events = [e async for e in stream_iter]

        delta_events = [e for e in events if e["type"] == "response.output_text.delta"]
        assert len(delta_events) > 0
        assert any(e["type"] == "response.created" for e in events)
        assert any(e["type"] == "response.completed" for e in events)


__all__ = [
    "TestStreamingOff",
    "TestStreamingOn",
    "TestStreamingWithToolCalls",
]
