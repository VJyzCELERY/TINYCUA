"""Unit tests for Stage 5 — Streaming.

Tests streaming with stream=True (normalized stream event passthrough) and
stream=False (string return), mocking the LLM call at the agent level.
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
    """Test stream=True yields normalized stream events."""

    @pytest.mark.asyncio
    async def test_stream_yields_normalized_events(self):
        """stream=True yields normalized events including deltas."""
        agent = Agent(llm_model=LanguageModel())

        raw_delta_event = {
            "type": "response.output_text.delta",
            "delta": "Hello",
            "index": 0,
        }

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                yield dict(raw_delta_event)

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("Say hello", stream=True)
        events = [e async for e in stream_iter]

        assert events[0]["type"] == "response.created"
        assert events[1]["type"] == "response.in_progress"
        assert events[2] == raw_delta_event
        assert events[-1]["type"] == "response.completed"


class TestStreamingWithToolCalls:
    """Test streaming with tool calls."""

    @pytest.mark.asyncio
    async def test_stream_tool_calls(self):
        """Tool call events pass through in stream; ready-gated execution works."""

        @tool
        def get_time() -> str:
            """Get the current time."""
            return "12:00"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        call_count = 0

        raw_tool_call_event = {
            "type": "response.output_item.added",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_time",
        }
        raw_arguments_event = {
            "type": "response.function_call_arguments.done",
            "id": "call_1",
            "arguments": "{}",
        }
        raw_ready_event = {
            "type": "tool_call.ready",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_time",
            "arguments": "{}",
        }
        raw_text_event = {
            "type": "response.output_text.delta",
            "delta": "The time is 12:00.",
            "index": 0,
        }

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield dict(raw_tool_call_event)
                    yield dict(raw_arguments_event)
                    yield dict(raw_ready_event)
                else:
                    yield dict(raw_text_event)

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("What time?", stream=True)
        events = [e async for e in stream_iter]

        # Verify the LLM was called twice (tool call → execution → follow-up)
        assert call_count == 2, f"Expected 2 LLM calls, got {call_count}"

        # Tool call events appear BEFORE tool execution resumes
        tool_event_types = {"response.output_item.added", "response.function_call_arguments.done", "tool_call.ready"}
        tool_indices = [
            i for i, e in enumerate(events) if e["type"] in tool_event_types
        ]
        text_indices = [
            i for i, e in enumerate(events) if e["type"] == "response.output_text.delta"
        ]
        if tool_indices and text_indices:
            assert max(tool_indices) < min(text_indices)
        assert any(e["type"] == "response.completed" for e in events)
        # Verify follow-up content exists after tool execution
        assert any(e["type"] == "response.output_text.delta" for e in events)

    @pytest.mark.asyncio
    async def test_arguments_done_without_ready_does_not_execute(self):
        """arguments.done without tool_call.ready does NOT trigger tool execution."""

        @tool
        def get_time() -> str:
            """Get the current time."""
            return "12:00"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        call_count = 0

        raw_tool_call_event = {
            "type": "response.output_item.added",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_time",
        }
        raw_arguments_event = {
            "type": "response.function_call_arguments.done",
            "id": "call_1",
            "arguments": "{}",
        }

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield dict(raw_tool_call_event)
                    yield dict(raw_arguments_event)
                # No tool_call.ready → tool is NOT executed → no second call

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("What time?", stream=True)
        events = [e async for e in stream_iter]

        # Only one LLM call — tool was NOT executed
        assert call_count == 1, f"Expected 1 LLM call (tool not executed), got {call_count}"
        # No content delta since tool wasn't executed to produce follow-up content
        assert not any(e["type"] == "response.output_text.delta" for e in events)


class TestProviderFailure:
    """Provider failure events must NOT be followed by synthetic response.completed."""

    @pytest.mark.asyncio
    async def test_response_failed_prevents_completed(self):
        """response.failed event blocks subsequent response.completed."""
        agent = Agent(llm_model=LanguageModel())

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created"}
                yield {"type": "response.failed", "error": {"message": "provider failed"}}

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("hi", stream=True)
        events = [e async for e in stream_iter]

        types = [e["type"] for e in events]
        assert "response.failed" in types
        failed_index = types.index("response.failed")
        assert not any(t == "response.completed" for t in types[failed_index + 1:]), (
            f"response.completed found after response.failed: {types}"
        )

    @pytest.mark.asyncio
    async def test_error_event_prevents_completed(self):
        """raw error event blocks subsequent response.completed."""
        agent = Agent(llm_model=LanguageModel())

        async def mock_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created"}
                yield {"type": "error", "error": {"message": "something went wrong"}}

            return _gen()

        agent._call_llm = mock_stream

        stream_iter = await agent.run("hi", stream=True)
        events = [e async for e in stream_iter]

        types = [e["type"] for e in events]
        assert "error" in types
        error_index = types.index("error")
        assert not any(t == "response.completed" for t in types[error_index + 1:]), (
            f"response.completed found after error: {types}"
        )


__all__ = [
    "TestStreamingOff",
    "TestStreamingOn",
    "TestStreamingWithToolCalls",
    "TestProviderFailure",
]
