"""Integration tests for Stage 5 — Streaming.

Tests all four streaming modes (off, token, event, all) and tool call
streaming, mocking the LLM call at the agent level.
"""

from __future__ import annotations

import pytest

from tinycua_sdk import Agent, LanguageModel, tool


class TestStreamingModeOff:
    """Test stream='off' returns a plain string."""

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

        result = await agent.run("Say hello", stream="off")
        assert isinstance(result, str)
        assert len(result) > 0


class TestStreamingModeToken:
    """Test stream='token' yields only token delta events."""

    @pytest.mark.asyncio
    async def test_token_yields_only_deltas(self):
        """token mode yields only response.output_text.delta events."""
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

        stream_iter = await agent.run("Say hello", stream="token")
        events = [e async for e in stream_iter]

        delta_events = [
            e
            for e in events
            if e["type"] not in ("response.created", "response.completed")
        ]
        assert all(e["type"] == "response.output_text.delta" for e in delta_events)
        assert any(e["type"] == "response.created" for e in events)
        assert any(e["type"] == "response.completed" for e in events)


class TestStreamingModeEvent:
    """Test stream='event' yields only lifecycle/tool events."""

    @pytest.mark.asyncio
    async def test_event_yields_no_deltas(self):
        """event mode yields agent events without token deltas."""
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

        stream_iter = await agent.run("Say hello", stream="event")
        events = [e async for e in stream_iter]

        delta_events = [e for e in events if e["type"] == "response.output_text.delta"]
        assert len(delta_events) == 0
        assert any(e["type"] == "response.created" for e in events)
        assert any(e["type"] == "response.completed" for e in events)


class TestStreamingModeAll:
    """Test stream='all' yields both token deltas and events."""

    @pytest.mark.asyncio
    async def test_all_yields_both(self):
        """all mode yields interleaved tokens and events."""
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

        stream_iter = await agent.run("Say hello", stream="all")
        events = [e async for e in stream_iter]

        delta_events = [e for e in events if e["type"] == "response.output_text.delta"]
        assert len(delta_events) > 0
        assert any(e["type"] == "response.created" for e in events)
        assert any(e["type"] == "response.completed" for e in events)


class TestStreamingWithToolCalls:
    """Test streaming with tool calls emits tool events."""

    @pytest.mark.asyncio
    async def test_stream_tool_calls_in_all_mode(self):
        """Tool call events appear in all streams."""

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

        stream_iter = await agent.run("What time?", stream="all")
        events = [e async for e in stream_iter]

        tool_events = [
            e for e in events if e.get("type") == "response.output_item.added"
        ]
        assert len(tool_events) >= 2  # at least tool_call + tool_output
        assert tool_events[0]["item"]["type"] == "tool_call"
        assert tool_events[0]["item"]["name"] == "get_time"

    @pytest.mark.asyncio
    async def test_stream_tool_calls_not_in_token_mode(self):
        """Tool call events should NOT appear in token mode."""

        @tool
        def get_time() -> str:
            """Get the current time."""
            return "12:00"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.tool_call.delta",
                    "id": "call_1",
                    "name": "get_time",
                    "arguments": "{}",
                }

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("What time?", stream="token")
        events = [e async for e in stream_iter]

        tool_events = [
            e for e in events if e.get("type") == "response.output_item.added"
        ]
        assert len(tool_events) == 0


__all__ = [
    "TestStreamingModeOff",
    "TestStreamingModeToken",
    "TestStreamingModeEvent",
    "TestStreamingModeAll",
    "TestStreamingWithToolCalls",
]
