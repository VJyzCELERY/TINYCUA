"""Tests for BaseLoop execution."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from unittest.mock import AsyncMock


from tinycua_sdk import Agent, AgentPolicy, BaseLoop, LanguageModel, Skill, tool
from tinycua_sdk.models.attachment import ContentPart, FileAttachment


class _EmptyAsyncStream(AsyncIterator[dict]):
    """Async iterator that yields no items (empty stream)."""

    async def __anext__(self):
        raise StopAsyncIteration


class TestBaseLoopBuildSystemMessage:
    """Test build_system_message method."""

    def test_build_system_message_with_instructions(self):
        agent = Agent(
            instructions="You are helpful.",
            llm_model=LanguageModel(),
        )
        loop = BaseLoop()
        msg = loop.build_system_message(agent)
        assert msg["role"] == "system"
        assert "You are helpful." in msg["content"]

    def test_build_system_message_with_override(self):
        agent = Agent(
            instructions="Original.",
            llm_model=LanguageModel(),
        )
        loop = BaseLoop()
        msg = loop.build_system_message(agent, "Override.")
        assert "Override." in msg["content"]
        assert "Original." not in msg["content"]

    def test_build_system_message_with_skills(self):
        skill = Skill(
            name="coder",
            description="Write code",
            instructions="Write clean code.",
        )
        agent = Agent(
            instructions="Be helpful.",
            llm_model=LanguageModel(),
            skills=[skill],
        )
        loop = BaseLoop()
        msg = loop.build_system_message(agent)
        assert "[coder]" in msg["content"]
        assert "Write clean code." in msg["content"]

    def test_build_system_message_no_instructions_no_skills(self):
        agent = Agent(llm_model=LanguageModel())
        loop = BaseLoop()
        msg = loop.build_system_message(agent)
        assert msg["content"] == ""


class TestBaseLoopRun:
    """Test BaseLoop.run() execution flow."""

    @pytest.mark.asyncio
    async def test_run_returns_content(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        agent._call_llm = AsyncMock(
            return_value={
                "content": "Hello, world!",
                "tool_calls": None,
                "usage": None,
            }
        )

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Say hi"}],
            tools=[],
        )
        assert result == "Hello, world!"
        agent._call_llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_with_tool_calls(self):
        @tool
        def get_time() -> str:
            return "12:00"

        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "get_time",
                            "arguments": "{}",
                        }
                    ],
                    "usage": None,
                }
            return {
                "content": "The time is 12:00.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "What time?"}],
            tools=[get_time],
        )
        assert result == "The time is 12:00."
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_stops_identical_consecutive_tool_calls(self):
        executions = 0

        @tool
        def fetch_page(url: str) -> str:
            nonlocal executions
            executions += 1
            return url

        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())
        calls = 0

        async def repeat_call(messages, tools):
            nonlocal calls
            calls += 1
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{calls}",
                        "name": "fetch_page",
                        "arguments": '{"url":"https://example.com"}',
                    }
                ],
            }

        agent._call_llm = repeat_call

        await loop.run(agent, messages=[], tools=[fetch_page])

        assert calls == 2
        assert executions == 1

    @pytest.mark.asyncio
    async def test_run_unknown_tool(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "nonexistent_tool",
                            "arguments": "{}",
                        }
                    ],
                    "usage": None,
                }
            return {
                "content": "Tool not found.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Do something"}],
            tools=[],
        )
        assert result == "Tool not found."
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_max_iterations(self):
        loop = BaseLoop(max_iterations=2)

        agent = Agent(
            llm_model=LanguageModel(),
            policy=AgentPolicy(max_tool_calls=100),
        )

        call_count = 0

        async def tool_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{call_count}",
                        "name": "dummy_tool",
                        "arguments": "{}",
                    }
                ],
                "usage": None,
            }

        @tool
        def dummy_tool() -> str:
            return "result"

        agent._call_llm = tool_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Keep going"}],
            tools=[dummy_tool],
        )
        assert call_count == 2
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_cancellation(self):
        loop = BaseLoop(max_iterations=10)
        agent = Agent(llm_model=LanguageModel())

        agent._cancelled = True

        with pytest.raises(asyncio.CancelledError):
            await loop.run(
                agent,
                messages=[{"role": "user", "content": "Cancel me"}],
                tools=[],
            )

    @pytest.mark.asyncio
    async def test_run_max_tool_calls_break(self):
        loop = BaseLoop(max_iterations=10)

        agent = Agent(
            llm_model=LanguageModel(),
            policy=AgentPolicy(max_tool_calls=2),
        )

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{call_count}",
                        "name": "dummy",
                        "arguments": "{}",
                    }
                ],
                "usage": None,
            }

        @tool
        def dummy() -> str:
            return "ok"

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Go"}],
            tools=[dummy],
        )
        assert call_count == 2
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_multiple_tool_calls_in_one_response(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def get_time() -> str:
            return "12:00"

        @tool
        def get_date() -> str:
            return "2026-05-07"

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "get_time",
                            "arguments": "{}",
                        },
                        {
                            "id": "call_2",
                            "name": "get_date",
                            "arguments": "{}",
                        },
                    ],
                    "usage": None,
                }
            return {
                "content": "The time is 12:00 and date is 2026-05-07.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "What time and date?"}],
            tools=[get_time, get_date],
        )
        assert result == "The time is 12:00 and date is 2026-05-07."
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_with_override_instructions(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(
            instructions="Original instructions.",
            llm_model=LanguageModel(),
        )

        captured_messages = []

        async def mock_call_llm(messages, tools):
            captured_messages.extend(messages)
            return {
                "content": "Done.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        await loop.run(
            agent,
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            override_instructions="Override instructions.",
        )

        assert any(
            "Override instructions." in m["content"]
            for m in captured_messages
            if m["role"] == "system"
        )
        assert not any(
            "Original instructions." in m["content"]
            for m in captured_messages
            if m["role"] == "system"
        )

    @pytest.mark.asyncio
    async def test_run_max_tool_calls_in_single_response(self):
        """Single response with 3 tool calls, max_tool_calls=2 -> only 2 executed."""
        loop = BaseLoop(max_iterations=5)
        policy = AgentPolicy(max_tool_calls=2)
        agent = Agent(llm_model=LanguageModel(), policy=policy)

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "search",
                            "arguments": '{"query": "a"}',
                        },
                        {
                            "id": "call_2",
                            "name": "search",
                            "arguments": '{"query": "b"}',
                        },
                        {
                            "id": "call_3",
                            "name": "search",
                            "arguments": '{"query": "c"}',
                        },
                    ],
                    "usage": None,
                }
            return {
                "content": "Done.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        @tool
        def search(query: str) -> str:
            return f"Result: {query}"

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Search"}],
            tools=[search],
        )
        assert call_count == 1
        assert result == "[max tool calls reached]"


class TestBaseLoopRunStream:
    """Test BaseLoop._run_stream() execution flow."""

    @pytest.mark.asyncio
    async def test_run_stream_yields_raw_events(self):
        """Streaming yields raw LLM events plus lifecycle events."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_text.delta",
                    "delta": "Hello",
                    "item_id": "1",
                }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed", "finish_reason": "completed"}
        assert any(e["type"] == "response.output_text.delta" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_provider_completed_dedup(self):
        """Only one response.completed when provider already emits it."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created", "response": {"id": "r_1"}}
                yield {"type": "response.output_text.delta", "delta": "Hi", "item_id": "1"}
                yield {"type": "response.completed", "finish_reason": "completed"}

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]
        completed_count = sum(
            1 for e in events if e.get("type") == "response.completed"
        )
        assert completed_count == 1, (
            f"Expected 1 response.completed, got {completed_count}: "
            f"{[e for e in events if e.get('type') == 'response.completed']}"
        )

    @pytest.mark.asyncio
    async def test_run_stream_first_chunk_response_failed(self):
        """First chunk is response.failed -> no synthetic response.completed."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.failed", "error": {"message": "boom"}}

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]
        types = [e["type"] for e in events]

        assert "response.failed" in types
        failed_index = types.index("response.failed")
        assert not any(t == "response.completed" for t in types[failed_index + 1:]), (
            f"response.completed found after response.failed: {types}"
        )

    @pytest.mark.asyncio
    async def test_run_stream_first_chunk_error(self):
        """First chunk is raw error -> no synthetic response.completed."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "error", "error": {"message": "oops"}}

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]
        types = [e["type"] for e in events]

        assert "error" in types
        error_index = types.index("error")
        assert not any(t == "response.completed" for t in types[error_index + 1:]), (
            f"response.completed found after error: {types}"
        )

    @pytest.mark.asyncio
    async def test_run_stream_first_chunk_completed_dedup(self):
        """First chunk is response.completed -> no synthetic duplicate."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.completed", "finish_reason": "completed"}

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]
        completed_count = sum(
            1 for e in events if e.get("type") == "response.completed"
        )
        assert completed_count == 1, (
            f"Expected 1 response.completed, got {completed_count}: "
            f"{[e for e in events if e.get('type') == 'response.completed']}"
        )

    @pytest.mark.asyncio
    async def test_run_stream_empty_llm_response(self):
        """Empty LLM stream completes cleanly with no intermediate events."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            return _EmptyAsyncStream()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [], [])
        events = [e async for e in stream_iter]
        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed", "finish_reason": "completed"}

    @pytest.mark.asyncio
    async def test_run_stream_with_tool_calls(self):
        """Tool calls execute and stream resumes with normalized events."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def get_time() -> str:
            return "12:00"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.output_item.added",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "response.function_call_arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "tool_call.ready",
                        "id": "call_1",
                        "call_id": "call_1",
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

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "time?"}], [get_time]
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed", "finish_reason": "completed"}
        delta_events = [
            e for e in events if e.get("type") == "response.output_text.delta"
        ]
        assert any("The time is 12:00." in e.get("delta", "") for e in delta_events)

    @pytest.mark.asyncio
    async def test_run_stream_stops_identical_consecutive_tool_calls(self):
        executions = 0

        @tool
        def get_time() -> str:
            nonlocal executions
            executions += 1
            return "12:00"

        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())
        calls = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal calls
                calls += 1
                yield {
                    "type": "tool_call.ready",
                    "id": f"call_{calls}",
                    "name": "get_time",
                    "arguments": "{}",
                }

            return _gen()

        agent._call_llm = fake_stream

        events = [event async for event in loop._run_stream(agent, [], [get_time])]

        assert calls == 2
        assert executions == 1
        assert events[-1]["finish_reason"] == "no_progress"

    @pytest.mark.asyncio
    async def test_run_stream_cancellation(self):
        """Cancellation during stream stops iteration."""
        loop = BaseLoop(max_iterations=10)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_text.delta",
                    "delta": "Hello",
                    "item_id": "1",
                }

            return _gen()

        agent._call_llm = fake_stream
        agent._cancelled = True

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]

        assert len(events) == 3
        assert events[0] == {"type": "response.created"}
        assert events[1] == {"type": "response.cancelled"}
        assert events[2] == {"type": "response.usage", "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

    @pytest.mark.asyncio
    async def test_run_stream_accumulates_tool_call_args(self):
        """Multi-chunk tool call arguments are accumulated and tool is executed correctly."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        cities_called: list[str] = []

        @tool
        def get_weather(city: str) -> str:
            cities_called.append(city)
            return f"Weather in {city}: sunny"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.output_item.added",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_weather",
                    }
                    yield {
                        "type": "response.function_call_arguments.delta",
                        "id": "call_1",
                        "arguments": '{"cit',
                    }
                    yield {
                        "type": "response.function_call_arguments.done",
                        "id": "call_1",
                        "arguments": '{"city": "Tokyo"}',
                    }
                    yield {
                        "type": "tool_call.ready",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_weather",
                        "arguments": '{"city": "Tokyo"}',
                    }
                else:
                    yield {
                        "type": "response.output_text.delta",
                        "delta": "It is sunny.",
                        "item_id": "2",
                    }

            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(
            agent,
            [{"role": "user", "content": "weather?"}],
            [get_weather],
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed", "finish_reason": "completed"}
        assert call_count == 2, f"Expected 2 LLM calls, got {call_count}"
        assert cities_called == ["Tokyo"], f"Expected tool called with Tokyo, got {cities_called}"
        text_deltas = [
            e for e in events if e.get("type") == "response.output_text.delta"
        ]
        assert len(text_deltas) == 1, f"Expected 1 text delta, got {len(text_deltas)}"
        assert text_deltas[0]["delta"] == "It is sunny."

    @pytest.mark.asyncio
    async def test_run_stream_accumulates_flow2_tool_call_args(self):
        """Normalized tool call events are accumulated and tool is executed correctly."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        cities_called: list[str] = []

        @tool
        def get_weather(city: str) -> str:
            cities_called.append(city)
            return f"Weather in {city}: sunny"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.output_item.added",
                        "id": "fc_1",
                        "call_id": "call_1",
                        "name": "get_weather",
                    }
                    yield {
                        "type": "response.function_call_arguments.delta",
                        "id": "fc_1",
                        "arguments": '{"cit',
                    }
                    yield {
                        "type": "response.function_call_arguments.done",
                        "id": "fc_1",
                        "arguments": '{"city": "Tokyo"}',
                    }
                    yield {
                        "type": "tool_call.ready",
                        "id": "fc_1",
                        "call_id": "call_1",
                        "name": "get_weather",
                        "arguments": '{"city": "Tokyo"}',
                    }
                else:
                    yield {
                        "type": "response.output_text.delta",
                        "delta": "Sunny in Tokyo.",
                        "item_id": "2",
                    }

            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(
            agent,
            [{"role": "user", "content": "weather?"}],
            [get_weather],
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed", "finish_reason": "completed"}
        assert call_count == 2, f"Expected 2 LLM calls, got {call_count}"
        assert cities_called == ["Tokyo"], f"Expected tool called with Tokyo, got {cities_called}"
        text_deltas = [
            e for e in events if e.get("type") == "response.output_text.delta"
        ]
        assert len(text_deltas) == 1, f"Expected 1 text delta, got {len(text_deltas)}"
        assert text_deltas[0]["delta"] == "Sunny in Tokyo."

    @pytest.mark.asyncio
    async def test_run_stream_max_iterations(self):
        """Stream stops after max_iterations."""
        loop = BaseLoop(max_iterations=1)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_item.added",
                    "id": "call_1",
                    "call_id": "call_1",
                    "name": "dummy_tool",
                }
                yield {
                    "type": "response.function_call_arguments.done",
                    "id": "call_1",
                    "arguments": "{}",
                }
                yield {
                    "type": "tool_call.ready",
                    "id": "call_1",
                    "call_id": "call_1",
                    "name": "dummy_tool",
                    "arguments": "{}",
                }

            return _gen()

        @tool
        def dummy_tool() -> str:
            return "result"

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "go"}], [dummy_tool]
        )
        events = [e async for e in stream_iter]

        assert any(e["type"] == "response.completed" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_emits_failed_on_exception(self):
        """response.failed event is emitted on stream failure."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def failing_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_text.delta",
                    "delta": "Hello",
                    "item_id": "msg_1",
                }
                raise RuntimeError("Stream failure")

            return _gen()

        agent._call_llm = failing_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        failed_events = [e for e in events if e["type"] == "response.failed"]
        error_events = [e for e in events if e["type"] == "error"]
        assert len(failed_events) == 1
        assert "message" in failed_events[0]["error"]
        assert len(error_events) == 1
        failed_idx = next(i for i, e in enumerate(events) if e["type"] == "response.failed")
        error_idx = next(i for i, e in enumerate(events) if e["type"] == "error")
        assert failed_idx < error_idx

    @pytest.mark.asyncio
    async def test_run_stream_emits_usage_event(self):
        """response.usage is emitted with cumulative usage."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_text.delta",
                    "delta": "Hello",
                    "item_id": "1",
                }
                yield {
                    "type": "response.usage",
                    "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
                }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], []
        )
        events = [e async for e in stream_iter]

        usage_events = [e for e in events if e["type"] == "response.usage"]
        assert len(usage_events) == 2  # raw event + cumulative summary
        assert usage_events[-1]["usage"]["total_tokens"] == 8
        assert usage_events[-1]["usage"]["input_tokens"] == 5
        assert usage_events[-1]["usage"]["output_tokens"] == 3

    @pytest.mark.asyncio
    async def test_run_stream_multi_iteration_cumulative_usage(self):
        """Cumulative usage sums across tool-call iterations."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def get_time() -> str:
            return "12:00"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.output_item.added",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "response.function_call_arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "tool_call.ready",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "response.usage",
                        "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
                    }
                else:
                    yield {
                        "type": "response.output_text.delta",
                        "delta": "The time is 12:00.",
                        "item_id": "2",
                    }
                    yield {
                        "type": "response.usage",
                        "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                    }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "time?"}], [get_time]
        )
        events = [e async for e in stream_iter]

        raw_usage = [e for e in events if e["type"] == "response.usage"]
        assert len(raw_usage) == 3  # iter1 raw + iter2 raw + cumulative summary

        cumulative = raw_usage[-1]
        assert cumulative["usage"]["input_tokens"] == 8
        assert cumulative["usage"]["output_tokens"] == 5
        assert cumulative["usage"]["total_tokens"] == 13

    @pytest.mark.asyncio
    async def test_run_stream_multi_iteration_usage_from_completed(self):
        """Usage from response.completed.response.usage accumulates across iterations."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def get_time() -> str:
            return "12:00"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.output_item.added",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "response.function_call_arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "tool_call.ready",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "response.completed",
                        "finish_reason": "tool_calls",
                        "response": {
                            "id": "r1",
                            "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
                        },
                    }
                else:
                    yield {
                        "type": "response.output_text.delta",
                        "delta": "The time is 12:00.",
                        "item_id": "2",
                    }
                    yield {
                        "type": "response.usage",
                        "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                    }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "time?"}], [get_time]
        )
        events = [e async for e in stream_iter]

        completed_events = [e for e in events if e["type"] == "response.completed"]
        usage_events = [e for e in events if e["type"] == "response.usage"]

        assert len(completed_events) == 1  # only the final SDK synthetic
        assert len(usage_events) == 2  # iter2 raw + cumulative summary

        cumulative = usage_events[-1]
        assert cumulative["usage"]["input_tokens"] == 8
        assert cumulative["usage"]["output_tokens"] == 5
        assert cumulative["usage"]["total_tokens"] == 13


class TestBaseLoopRunStreamInProgress:
    """Tests for response.in_progress event emission."""

    @pytest.mark.asyncio
    async def test_in_progress_emitted_before_delta(self):
        """SDK emits response.in_progress before first delta when provider emits none."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.output_text.delta", "delta": "Hi", "item_id": "1"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        event_types = [e["type"] for e in events]

        assert event_types.index("response.created") < event_types.index("response.in_progress")
        assert event_types.index("response.in_progress") < event_types.index("response.output_text.delta")

    @pytest.mark.asyncio
    async def test_in_progress_not_duplicated_when_provider_emits(self):
        """SDK does not inject duplicate response.in_progress when provider already emits it."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created", "response": {"id": "r_1"}}
                yield {"type": "response.in_progress"}
                yield {"type": "response.output_text.delta", "delta": "Hi", "item_id": "1"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        in_progress_count = sum(1 for e in events if e["type"] == "response.in_progress")

        assert in_progress_count == 1

    @pytest.mark.asyncio
    async def test_in_progress_injected_after_provider_response_created(self):
        """SDK injects response.in_progress when provider emits response.created but not in_progress."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created", "response": {"id": "r_1"}}
                yield {"type": "response.output_text.delta", "delta": "Hi", "item_id": "1"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        event_types = [e["type"] for e in events]

        assert event_types.index("response.created") < event_types.index("response.in_progress")
        assert event_types.index("response.in_progress") < event_types.index("response.output_text.delta")

    @pytest.mark.asyncio
    async def test_no_in_progress_after_completed_first_chunk(self):
        """response.in_progress is NOT emitted when first chunk is response.completed."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.completed", "finish_reason": "completed"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        assert not any(e["type"] == "response.in_progress" for e in events)

    @pytest.mark.asyncio
    async def test_no_in_progress_after_failed_first_chunk(self):
        """response.in_progress is NOT emitted when first chunk is response.failed."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.failed", "error": {"message": "boom"}}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        assert not any(e["type"] == "response.in_progress" for e in events)

    @pytest.mark.asyncio
    async def test_no_in_progress_after_error_first_chunk(self):
        """response.in_progress is NOT emitted when first chunk is error."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "error", "error": {"message": "oops"}}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        assert not any(e["type"] == "response.in_progress" for e in events)

    @pytest.mark.asyncio
    async def test_in_progress_in_each_iteration(self):
        """Each LLM call iteration gets its own response.in_progress."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def dummy_tool() -> str:
            return "result"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.output_item.added",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "dummy_tool",
                    }
                    yield {
                        "type": "response.function_call_arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "tool_call.ready",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "dummy_tool",
                        "arguments": "{}",
                    }
                else:
                    yield {"type": "response.output_text.delta", "delta": "Done.", "item_id": "2"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "go"}], [dummy_tool])
        events = [e async for e in stream_iter]
        in_progress_count = sum(1 for e in events if e["type"] == "response.in_progress")

        # Two LLM iterations -> two response.in_progress events
        assert in_progress_count == 2


class TestLoopExecution:
    """Tests for loop execution (mocked LLM)."""

    @pytest.mark.asyncio
    async def test_run_basic(self, mock_llm_client):
        """Basic run with mocked LLM."""
        agent = Agent(llm_model=LanguageModel())
        response = await agent.run("Hello")
        assert response == "Mocked response"

    @pytest.mark.asyncio
    async def test_run_with_messages(self, mock_llm_client):
        """Pass message history."""
        agent = Agent(llm_model=LanguageModel())
        messages = [{"role": "user", "content": "Previous"}]
        response = await agent.run("Hello", messages=messages)
        assert response == "Mocked response"

    @pytest.mark.asyncio
    async def test_run_with_tools(self, mock_llm_with_tool_calls):
        """Tool calling in loop (mocked LLM returns tool call JSON)."""

        @tool
        def search(query: str) -> str:
            """Search for something."""
            return f"Results: {query}"

        agent = Agent(llm_model=LanguageModel(), tools=[search])
        response = await agent.run("Search for quantum")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_run_stateless(self, mock_llm_client):
        """Multiple runs are independent."""
        agent = Agent(llm_model=LanguageModel())
        r1 = await agent.run("Query 1")
        r2 = await agent.run("Query 2")
        assert r1 == "Mocked response"
        assert r2 == "Mocked response"

    @pytest.mark.asyncio
    async def test_custom_loop(self, mock_llm_client):
        """Agent with custom BaseLoop subclass."""

        class CustomLoop(BaseLoop):
            async def run(
                self, agent, messages, tools, override_instructions=None, **kwargs
            ):
                return "Custom result"

        agent = Agent(llm_model=LanguageModel(), loop=CustomLoop())
        response = await agent.run("Hello")
        assert response == "Custom result"

    @pytest.mark.asyncio
    async def test_base_loop_default(self, mock_llm_client):
        """Default BaseLoop() used when loop=None."""
        agent = Agent(llm_model=LanguageModel())
        response = await agent.run("Hello")
        assert response == "Mocked response"


class TestNormalizeToolResult:
    """Unit tests for normalize_tool_result helper."""

    def test_normalize_structured_multipart_content(self):
        """Rule 1: Non-empty list of ContentParts is treated as structured multipart."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        tool_result = {"content": [ContentPart(type="text", text="hello")]}
        result = normalize_tool_result("call_1", tool_result)
        assert result["role"] == "tool_result"
        assert result["call_id"] == "call_1"
        assert result["content"] == tool_result["content"]

    def test_normalize_raw_dict_content_parts(self):
        """Rule 1 (raw dicts): Raw dicts matching ContentPart shape are structured."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        tool_result = {"content": [{"type": "text", "text": "hello"}]}
        result = normalize_tool_result("call_1", tool_result)
        assert result["role"] == "tool_result"
        assert result["call_id"] == "call_1"
        assert result["content"] == tool_result["content"]

    def test_normalize_string_with_attachments(self):
        """Rule 2: String content plus attachments list yields structured message."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        attachment = FileAttachment.from_bytes(
            b"data", mime_type="text/plain", filename="f.txt",
        )
        tool_result = {"content": "Generated file.", "attachments": [attachment]}
        result = normalize_tool_result("call_1", tool_result)
        assert result["content"] == "Generated file."
        assert result["attachments"] == [attachment]

    def test_normalize_legacy_content_dict_without_attachments_falls_back_to_string(
        self,
    ):
        """Legacy dict with string content but no attachments/canonical marker.

        FR-008: A legacy dict such as ``{"content": "kept", "metadata": {...}}``
        must be stringified as a whole, not have its extra keys dropped.
        """
        from tinycua_sdk.agent.loop import normalize_tool_result

        value = {"content": "kept", "metadata": {"id": 1}}
        result = normalize_tool_result("call_1", value)
        assert result["content"] == str(value)
        assert "attachments" not in result

    @pytest.mark.parametrize(
        "scalar_content",
        [42, 3.14, True, None],
    )
    def test_normalize_legacy_scalar_content_dict_falls_back_to_string(
        self, scalar_content,
    ):
        """Legacy dict with scalar (non-string, non-list) content stringified.

        FR-008: A legacy dict such as ``{"content": 42, "metadata": {...}}``
        must be stringified as a whole, not raise ValueError.  Only canonical
        or attachment-bearing dicts reject scalar content.
        """
        from tinycua_sdk.agent.loop import normalize_tool_result

        value = {"content": scalar_content, "metadata": {"id": 1}}
        result = normalize_tool_result("call_1", value)
        assert result["content"] == str(value)
        assert "attachments" not in result

    def test_normalize_pre_formed_canonical_message(self):
        """Rule 3: Tool result with role='tool_result' is treated as canonical."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        tool_result = {
            "role": "tool_result",
            "call_id": "call_abc",
            "content": "Canonical content.",
        }
        result = normalize_tool_result("call_1", tool_result)
        assert result["role"] == "tool_result"
        assert result["call_id"] == "call_1"
        assert result["content"] == "Canonical content."

    @pytest.mark.parametrize(
        "legacy_value",
        [
            "plain string",
            42,
            {"arbitrary": "dict", "nested": {"key": "val"}},
            None,
        ],
    )
    def test_normalize_legacy_falls_back_to_string(self, legacy_value):
        """Rule 4: Unrecognized tool result shapes fall back to str(tool_result)."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        result = normalize_tool_result("call_1", legacy_value)
        assert result["content"] == str(legacy_value)
        assert "attachments" not in result

    @pytest.mark.parametrize("empty_content", [[], list()])
    def test_normalize_rejects_empty_content_part_list(self, empty_content):
        """Rule 5: Empty content list raises ValueError."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        tool_result = {"content": empty_content}
        with pytest.raises(ValueError, match="empty"):
            normalize_tool_result("call_1", tool_result)

    def test_normalize_legacy_list_content_dict_falls_back_to_string(self):
        """FR-008 legacy dict with arbitrary list-valued content stringified.

        A legacy dict like ``{"content": ["legacy item"], "metadata": {"id": 1}}``
        that is not canonical (no ``role: "tool_result"``) and has no attachments
        MUST fall back to ``str(tool_result)``, not raise ValueError.
        """
        from tinycua_sdk.agent.loop import normalize_tool_result

        value = {"content": ["legacy item"], "metadata": {"id": 1}}
        result = normalize_tool_result("call_1", value)
        assert result["content"] == str(value)
        assert "attachments" not in result

    def test_normalize_invalid_content_part_in_canonical_dict_raises(self):
        """Invalid ContentPart items in canonical/attachment dicts still raise ValueError."""
        from tinycua_sdk.agent.loop import normalize_tool_result

        # Canonical dict with invalid list content
        canonical = {
            "role": "tool_result",
            "content": [{"type": "unknown_type", "value": "x"}],
        }
        with pytest.raises(ValueError, match="content list"):
            normalize_tool_result("call_1", canonical)

        # Attachment-bearing dict with invalid list content
        attachment = FileAttachment.from_bytes(
            b"data", mime_type="image/png", filename="test.png",
        )
        with_attachments = {
            "content": [{"type": "unknown_type", "value": "x"}],
            "attachments": [attachment],
        }
        with pytest.raises(ValueError, match="content list"):
            normalize_tool_result("call_1", with_attachments)
