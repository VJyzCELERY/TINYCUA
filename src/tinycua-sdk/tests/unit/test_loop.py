"""Tests for BaseLoop execution."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from tinycua_sdk import Agent, AgentPolicy, BaseLoop, LanguageModel, Skill, tool


class TestBaseLoopBuildSystemMessage:
    """Test _build_system_message method."""

    def test_build_system_message_with_instructions(self):
        agent = Agent(
            instructions="You are helpful.",
            llm_model=LanguageModel(),
        )
        loop = BaseLoop()
        msg = loop._build_system_message(agent)
        assert msg["role"] == "system"
        assert "You are helpful." in msg["content"]

    def test_build_system_message_with_override(self):
        agent = Agent(
            instructions="Original.",
            llm_model=LanguageModel(),
        )
        loop = BaseLoop()
        msg = loop._build_system_message(agent, "Override.")
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
        msg = loop._build_system_message(agent)
        assert "[coder]" in msg["content"]
        assert "Write clean code." in msg["content"]

    def test_build_system_message_no_instructions_no_skills(self):
        agent = Agent(llm_model=LanguageModel())
        loop = BaseLoop()
        msg = loop._build_system_message(agent)
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
                            "type": "function",
                            "function": {
                                "name": "get_time",
                                "arguments": "{}",
                            },
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
                            "type": "function",
                            "function": {
                                "name": "nonexistent_tool",
                                "arguments": "{}",
                            },
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
                        "type": "function",
                        "function": {
                            "name": "dummy_tool",
                            "arguments": "{}",
                        },
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
                        "type": "function",
                        "function": {
                            "name": "dummy",
                            "arguments": "{}",
                        },
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
                            "type": "function",
                            "function": {"name": "get_time", "arguments": "{}"},
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "get_date", "arguments": "{}"},
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
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": '{"query": "a"}',
                            },
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": '{"query": "b"}',
                            },
                        },
                        {
                            "id": "call_3",
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": '{"query": "c"}',
                            },
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
    async def test_run_stream_token_yields_only_deltas(self):
        """token mode yields only response.output_text.delta events."""
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
            agent, [{"role": "user", "content": "hi"}], [], stream_mode="token"
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed"}
        assert any(e["type"] == "response.output_text.delta" for e in events)
        assert not any(e["type"] == "response.output_item.added" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_event_yields_only_lifecycle_events(self):
        """event mode yields lifecycle/tool events, no delta events."""
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
            agent, [{"role": "user", "content": "hi"}], [], stream_mode="event"
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed"}
        assert not any(e["type"] == "response.output_text.delta" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_all_yields_both_deltas_and_events(self):
        """all mode yields both delta and lifecycle events."""
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
            agent, [{"role": "user", "content": "hi"}], [], stream_mode="all"
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed"}
        assert any(e["type"] == "response.output_text.delta" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_with_tool_calls(self):
        """Tool calls yield output_item.added events and stream resumes."""
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

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "time?"}], [get_time], stream_mode="all"
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed"}
        tool_events = [
            e for e in events if e.get("type") == "response.output_item.added"
        ]
        assert any(t["item"]["type"] == "tool_call" for t in tool_events)
        assert any(t["item"]["type"] == "tool_output" for t in tool_events)
        delta_events = [
            e for e in events if e.get("type") == "response.output_text.delta"
        ]
        assert any("The time is 12:00." in e.get("delta", "") for e in delta_events)

    @pytest.mark.asyncio
    async def test_run_stream_mode_filters_tool_events(self):
        """token mode does NOT yield tool events."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def get_time() -> str:
            return "12:00"

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.tool_call.delta",
                    "index": 0,
                    "id": "call_1",
                    "name": "get_time",
                    "arguments": "{}",
                }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent,
            [{"role": "user", "content": "time?"}],
            [get_time],
            stream_mode="token",
        )
        events = [e async for e in stream_iter]

        tool_events = [
            e for e in events if e.get("type") == "response.output_item.added"
        ]
        assert len(tool_events) == 0

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
            agent, [{"role": "user", "content": "hi"}], [], stream_mode="token"
        )
        events = [e async for e in stream_iter]

        assert len(events) == 2
        assert events[0] == {"type": "response.created"}
        assert events[1] == {"type": "response.cancelled"}

    @pytest.mark.asyncio
    async def test_run_stream_accumulates_tool_call_args(self):
        """Multi-chunk tool call arguments are accumulated correctly."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        @tool
        def get_weather(city: str) -> str:
            return f"Weather in {city}: sunny"

        call_count = 0

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield {
                        "type": "response.tool_call.delta",
                        "index": 0,
                        "id": "call_1",
                        "name": "get_weather",
                        "arguments": '{"cit',
                    }
                    yield {
                        "type": "response.tool_call.delta",
                        "index": 0,
                        "id": "call_1",
                        "name": "",
                        "arguments": 'y": "Tokyo"}',
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
            stream_mode="all",
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        assert events[-1] == {"type": "response.completed"}
        tool_outputs = [
            e
            for e in events
            if e.get("type") == "response.output_item.added"
            and e["item"]["type"] == "tool_output"
        ]
        assert len(tool_outputs) == 1
        assert "sunny" in tool_outputs[0]["item"]["output"]

    @pytest.mark.asyncio
    async def test_run_stream_max_iterations(self):
        """Stream stops after max_iterations."""
        loop = BaseLoop(max_iterations=1)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.tool_call.delta",
                    "index": 0,
                    "id": "call_1",
                    "name": "dummy_tool",
                    "arguments": "{}",
                }

            return _gen()

        @tool
        def dummy_tool() -> str:
            return "result"

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "go"}], [dummy_tool], stream_mode="all"
        )
        events = [e async for e in stream_iter]

        assert any(e["type"] == "response.completed" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_emits_output_text_done(self):
        """response.output_text.done is emitted with accumulated text."""
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        async def fake_stream(messages, tools, stream=False):
            async def _gen():
                yield {
                    "type": "response.output_text.delta",
                    "delta": "Hello",
                    "item_id": "msg_1",
                }
                yield {
                    "type": "response.output_text.delta",
                    "delta": " world",
                    "item_id": "msg_1",
                }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent, [{"role": "user", "content": "hi"}], [], stream_mode="event"
        )
        events = [e async for e in stream_iter]

        done_events = [e for e in events if e["type"] == "response.output_text.done"]
        assert len(done_events) == 1
        assert done_events[0]["content"] == "Hello world"
        assert done_events[0]["item_id"] == "msg_1"

    @pytest.mark.asyncio
    async def test_run_stream_emits_output_item_done(self):
        """response.output_item.done is emitted after text and tool items."""
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
                        "item_id": "msg_2",
                    }

            return _gen()

        agent._call_llm = fake_stream

        stream_iter = loop._run_stream(
            agent,
            [{"role": "user", "content": "time?"}],
            [get_time],
            stream_mode="all",
        )
        events = [e async for e in stream_iter]

        done_events = [e for e in events if e["type"] == "response.output_item.done"]
        assert len(done_events) == 3  # text, tool_call, tool_output
        types = [e["item"]["type"] for e in done_events]
        assert "text" in types
        assert "tool_call" in types
        assert "tool_output" in types

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
            agent, [{"role": "user", "content": "hi"}], [], stream_mode="all"
        )
        events = [e async for e in stream_iter]

        assert events[0] == {"type": "response.created"}
        failed_events = [e for e in events if e["type"] == "response.failed"]
        error_events = [e for e in events if e["type"] == "error"]
        assert len(failed_events) == 1
        assert "message" in failed_events[0]["error"]
        assert len(error_events) == 0
        assert events[-1]["type"] == "response.failed"
