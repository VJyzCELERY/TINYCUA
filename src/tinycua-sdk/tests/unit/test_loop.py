"""Tests for BaseLoop execution."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from unittest.mock import AsyncMock


from tinycua_sdk import Agent, AgentPolicy, BaseLoop, LanguageModel, Skill, tool


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
                    "type": "content.delta",
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
        assert any(e["type"] == "content.delta" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_provider_completed_dedup(self):
        """Only one response.completed when provider already emits it."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created", "response": {"id": "r_1"}}
                yield {"type": "content.delta", "delta": "Hi", "item_id": "1"}
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
                        "type": "tool_call.started",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                else:
                    yield {
                        "type": "content.delta",
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
            e for e in events if e.get("type") == "content.delta"
        ]
        assert any("The time is 12:00." in e.get("delta", "") for e in delta_events)

    @pytest.mark.asyncio
    async def test_run_stream_cancellation(self):
        """Cancellation during stream stops iteration."""
        loop = BaseLoop(max_iterations=10)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "content.delta",
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
                        "type": "tool_call.started",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_weather",
                    }
                    yield {
                        "type": "tool_call.arguments.delta",
                        "id": "call_1",
                        "arguments": '{"cit',
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "call_1",
                        "arguments": '{"city": "Tokyo"}',
                    }
                else:
                    yield {
                        "type": "content.delta",
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
            e for e in events if e.get("type") == "content.delta"
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
                        "type": "tool_call.started",
                        "id": "fc_1",
                        "call_id": "call_1",
                        "name": "get_weather",
                    }
                    yield {
                        "type": "tool_call.arguments.delta",
                        "id": "fc_1",
                        "arguments": '{"cit',
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "fc_1",
                        "arguments": '{"city": "Tokyo"}',
                    }
                else:
                    yield {
                        "type": "content.delta",
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
            e for e in events if e.get("type") == "content.delta"
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
                    "type": "tool_call.started",
                    "id": "call_1",
                    "call_id": "call_1",
                    "name": "dummy_tool",
                }
                yield {
                    "type": "tool_call.arguments.done",
                    "id": "call_1",
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
                    "type": "content.delta",
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
                    "type": "content.delta",
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
                        "type": "tool_call.started",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "response.usage",
                        "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
                    }
                else:
                    yield {
                        "type": "content.delta",
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
                        "type": "tool_call.started",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                    yield {
                        "type": "response.completed",
                        "response": {
                            "id": "r1",
                            "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
                        },
                    }
                else:
                    yield {
                        "type": "content.delta",
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

        assert len(completed_events) == 2  # provider forwarded + SDK synthetic
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
                yield {"type": "content.delta", "delta": "Hi", "item_id": "1"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        event_types = [e["type"] for e in events]

        assert event_types.index("response.created") < event_types.index("response.in_progress")
        assert event_types.index("response.in_progress") < event_types.index("content.delta")

    @pytest.mark.asyncio
    async def test_in_progress_not_duplicated_when_provider_emits(self):
        """SDK does not inject duplicate response.in_progress when provider already emits it."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {"type": "response.created", "response": {"id": "r_1"}}
                yield {"type": "response.in_progress"}
                yield {"type": "content.delta", "delta": "Hi", "item_id": "1"}
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
                yield {"type": "content.delta", "delta": "Hi", "item_id": "1"}
            return _gen()

        agent._call_llm = fake_stream
        stream_iter = loop._run_stream(agent, [{"role": "user", "content": "hi"}], [])
        events = [e async for e in stream_iter]
        event_types = [e["type"] for e in events]

        assert event_types.index("response.created") < event_types.index("response.in_progress")
        assert event_types.index("response.in_progress") < event_types.index("content.delta")

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
                        "type": "tool_call.started",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "dummy_tool",
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }
                else:
                    yield {"type": "content.delta", "delta": "Done.", "item_id": "2"}
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
