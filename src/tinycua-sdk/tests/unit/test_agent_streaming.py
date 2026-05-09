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

        raw_delta_event = {
            "type": "response.output_text.delta",
            "delta": "Hello",
            "item_id": "1",
        }

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                yield dict(raw_delta_event)

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("Say hello", stream=True)
        events = [e async for e in stream_iter]

        assert events[0]["type"] == "response.created"
        assert events[1] == raw_delta_event
        assert events[-1]["type"] == "response.completed"


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

        raw_tool_call_event = {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "id": "call_1", "call_id": "call_1", "name": "get_time"},
        }
        raw_arguments_event = {
            "type": "response.function_call_arguments.done",
            "item_id": "call_1",
            "name": "get_time",
            "arguments": "{}",
        }
        raw_text_event = {
            "type": "response.output_text.delta",
            "delta": "The time is 12:00.",
            "item_id": "2",
        }

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield dict(raw_tool_call_event)
                    yield dict(raw_arguments_event)
                else:
                    yield dict(raw_text_event)

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("What time?", stream=True)
        events = [e async for e in stream_iter]

        # Tool call events appear BEFORE tool execution resumes
        tool_event_types = {"response.output_item.added", "response.function_call_arguments.done"}
        tool_indices = [
            i for i, e in enumerate(events) if e["type"] in tool_event_types
        ]
        text_indices = [
            i for i, e in enumerate(events) if e["type"] == "response.output_text.delta"
        ]
        if tool_indices and text_indices:
            assert max(tool_indices) < min(text_indices)
        assert any(e["type"] == "response.completed" for e in events)


__all__ = [
    "TestStreamingOff",
    "TestStreamingOn",
    "TestStreamingWithToolCalls",
]
