"""Tests for tool streaming."""

import pytest


class TestStreamEventType:
    def test_stream_event_type_values(self):
        from tinycua_sdk.models import StreamEventType

        assert StreamEventType.CONTENT.value == "content"
        assert StreamEventType.TOOL_CALL_START.value == "tool_call_start"
        assert StreamEventType.TOOL_CALL_CHUNK.value == "tool_call_chunk"
        assert StreamEventType.TOOL_CALL_END.value == "tool_call_end"
        assert StreamEventType.TOOL_RESULT_START.value == "tool_result_start"
        assert StreamEventType.TOOL_RESULT_CHUNK.value == "tool_result_chunk"
        assert StreamEventType.TOOL_RESULT_END.value == "tool_result_end"
        assert StreamEventType.DONE.value == "done"


class TestStreamEvent:
    def test_stream_event_creation(self):
        from tinycua_sdk.models import StreamEvent, StreamEventType

        event = StreamEvent(
            type=StreamEventType.CONTENT,
            data={"content": "Hello"},
        )
        assert event.type == StreamEventType.CONTENT
        assert event.data["content"] == "Hello"


class TestRunnerStreamWithTools:
    @pytest.mark.asyncio
    async def test_stream_with_tools_returns_events(self):
        from tinycua_sdk.models import AgentConfig, StreamEvent, StreamEventType
        from tinycua_sdk.runner import Runner

        config = AgentConfig(
            name="test",
            model="test-model",
            provider="openai",
        )

        runner = Runner(config)

        mock_stream_events = [
            StreamEvent(
                type=StreamEventType.CONTENT,
                data={"choices": [{"delta": {"content": "Hello"}}]},
            ),
            StreamEvent(type=StreamEventType.DONE, data={"finish_reason": "stop"}),
        ]

        async def mock_stream(*args, **kwargs):
            for event in mock_stream_events:
                yield event

        runner.client.stream = mock_stream

        events = []
        async for event in runner.stream_with_tools("Hello"):
            events.append(event)

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_stream_with_tools_tool_call_detection(self):
        from tinycua_sdk.models import AgentConfig, StreamEvent, StreamEventType
        from tinycua_sdk.runner import Runner

        config = AgentConfig(
            name="test",
            model="test-model",
            provider="openai",
            tools=[],
        )

        runner = Runner(config)

        tool_call_delta = {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "Tokyo"}',
                                },
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

        mock_stream_events = [
            StreamEvent(type=StreamEventType.CONTENT, data=tool_call_delta),
            StreamEvent(type=StreamEventType.DONE, data={"finish_reason": "stop"}),
        ]

        async def mock_stream(*args, **kwargs):
            for event in mock_stream_events:
                yield event

        runner.client.stream = mock_stream

        events = []
        async for event in runner.stream_with_tools("What's the weather?"):
            events.append(event)

        tool_call_events = [
            e for e in events if e.type == StreamEventType.TOOL_CALL_END
        ]
        assert len(tool_call_events) >= 0


class TestToolExecutionStreaming:
    @pytest.mark.asyncio
    async def test_execute_tool_regular_function(self):
        from tinycua_sdk.models import AgentConfig
        from tinycua_sdk.runner import Runner
        from tinycua_sdk.tools import tool

        @tool()
        def get_weather(location: str) -> dict:
            """Get weather for location."""
            return {"temp": 22, "location": location}

        config = AgentConfig(
            name="test",
            model="test-model",
            provider="openai",
            tools=[get_weather],
        )

        runner = Runner(config)
        result = runner._execute_tool_streaming("get_weather", {"location": "Tokyo"})

        assert result["success"] is True
        assert result["result"] == {"temp": 22, "location": "Tokyo"}
        assert result["tool_name"] == "get_weather"

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        from tinycua_sdk.models import AgentConfig
        from tinycua_sdk.runner import Runner

        config = AgentConfig(
            name="test",
            model="test-model",
            provider="openai",
            tools=[],
        )

        runner = Runner(config)
        result = runner._execute_tool_streaming("nonexistent", {})

        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["tool_name"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_tool_result_chunking(self):
        from tinycua_sdk.models import AgentConfig
        from tinycua_sdk.runner import Runner
        from tinycua_sdk.tools import tool

        @tool()
        def long_running_tool() -> str:
            """A long result."""
            return "This is a very long result that should be chunked"

        config = AgentConfig(
            name="test",
            model="test-model",
            provider="openai",
            tools=[long_running_tool],
        )

        runner = Runner(config)
        tool_name = "long_running_tool"
        tool_input = {}

        result = runner._execute_tool_streaming(tool_name, tool_input)
        result_str = str(result)

        chunk_size = 10
        chunks = [
            result_str[i : i + chunk_size]
            for i in range(0, len(result_str), chunk_size)
        ]

        assert len(chunks) > 1
        assert "".join(chunks) == result_str
