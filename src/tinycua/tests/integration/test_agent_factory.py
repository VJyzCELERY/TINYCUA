"""Integration tests for Agent Factory Contract (Milestone 1.1)."""

import pytest
from unittest.mock import AsyncMock
from tinycua_sdk.agent import Agent, BaseLoop
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node import NodeExecutionError
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session

ROUTE_PASSTHROUGH = (
    '{"tool_calls":[{"name":"select_query_route","arguments":{"route":"passthrough"}}]}'
)


class TestCreateTinyCUAAgent:
    """Tests for the create_tinycua_agent factory function."""

    def test_factory_returns_agent_with_tinycua_loop(self):
        """Factory returns SDK Agent with TinyCUALoop attached."""
        agent = create_tinycua_agent()
        assert isinstance(agent, Agent)
        assert isinstance(agent.loop, TinyCUALoop)
        assert isinstance(agent.loop, BaseLoop)

    def test_factory_creates_new_session_when_none(self):
        """When no session provided, factory creates a new root session."""
        agent = create_tinycua_agent()
        loop = agent.loop
        assert isinstance(loop.root_session, Session)
        assert loop.root_session.session_id is not None

    def test_factory_uses_provided_session(self):
        """When session is provided, factory uses it."""
        session = Session()
        agent = create_tinycua_agent(session=session)
        assert agent.loop.root_session is session

    def test_factory_applies_session_config(self):
        """Provided SessionConfig is applied to the session."""
        config = SessionConfig(max_context_messages=100)
        agent = create_tinycua_agent(session_config=config)
        assert agent.loop.session_config == config
        assert agent.loop.root_session.session_config == config

    def test_factory_accepts_agent_kwargs(self):
        """Factory passes **agent_kwargs through to SDK Agent."""
        agent = create_tinycua_agent(name="test-agent", instructions="Be helpful")
        assert agent.name == "test-agent"
        assert agent.instructions == "Be helpful"

    def test_tinycua_loop_extends_base_loop(self):
        """TinyCUALoop is a subclass of SDK BaseLoop."""
        session = Session()
        loop = TinyCUALoop(root_session=session)
        assert isinstance(loop, BaseLoop)


class TestAgentRun:
    """Tests for agent.run() through the full factory -> agent -> loop chain."""

    @pytest.mark.asyncio
    async def test_run_returns_string_when_not_streaming(self):
        """agent.run() returns string when stream=False."""
        agent = create_tinycua_agent()
        agent._call_llm = AsyncMock(
            side_effect=[
                {
                    "content": ROUTE_PASSTHROUGH,
                    "tool_calls": [],
                },
                {
                    "content": "Hello",
                    "tool_calls": None,
                    "usage": None,
                    "finish_reason": "completed",
                    "model": None,
                },
            ]
        )
        result = await agent.run("hello")
        assert isinstance(result, str)
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_run_returns_async_iterator_when_streaming(self):
        """agent.run() returns async iterator when stream=True."""
        agent = create_tinycua_agent()

        # Note: _call_llm for streaming must return an AsyncIterator.
        # A bare async generator function works because calling it returns
        # an AsyncGenerator (which is an AsyncIterator). This is structurally
        # different from the non-streaming mock which uses AsyncMock, because
        # the non-streaming path expects a dict return value.
        call_count = 0

        async def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {
                    "type": "response.tool_call",
                    "id": "call_route",
                    "function": {
                        "name": "select_query_route",
                        "arguments": '{"route":"passthrough"}',
                    },
                }
                yield {"type": "response.completed", "finish_reason": "completed"}
                return
            yield {"type": "response.output_text.delta", "delta": "Hi"}
            yield {"type": "response.completed", "finish_reason": "completed"}

        agent._call_llm = mock_stream
        result = await agent.run("hello", stream=True)
        assert hasattr(result, "__aiter__")
        events = [e async for e in result]
        assert len(events) > 0
        # Find the delta event (may be preceded by lifecycle events)
        delta_events = [
            e for e in events if e.get("type") == "response.output_text.delta"
        ]
        assert len(delta_events) > 0
        assert delta_events[0]["delta"] == "Hi"
        session = agent.loop.root_session
        # chat_history now includes tool_result records (route-tool execution);
        # filter for the assistant record the test cares about.
        assistant_records = [r for r in session.chat_history if r.role == "assistant"]
        assert len(assistant_records) == 1
        assert assistant_records[0].content == "Hi"
        assert session.input_context[0]["role"] == "user"
        assert session.input_context[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_run_populates_session_chat_history(self):
        """agent.run() records assistant responses in session chat history.

        User messages are stored in input_context, not chat_history.
        """
        agent = create_tinycua_agent()
        agent._call_llm = AsyncMock(
            side_effect=[
                {"content": ROUTE_PASSTHROUGH, "tool_calls": []},
                {
                    "content": "Hello",
                    "tool_calls": None,
                    "usage": None,
                    "finish_reason": "completed",
                    "model": None,
                },
            ]
        )
        await agent.run("hello")
        session = agent.loop.root_session
        # chat_history now includes tool_result records (route-tool execution);
        # filter for the assistant record the test cares about.
        assistant_records = [r for r in session.chat_history if r.role == "assistant"]
        assert len(assistant_records) == 1
        assert assistant_records[0].content == "Hello"
        assert session.input_context[0]["role"] == "user"
        assert session.input_context[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_run_does_not_record_empty_assistant_response(self):
        """Empty terminal responses fail validation instead of becoming final."""
        from dataclasses import replace

        from tinycua.factory import create_default_queue

        agent = create_tinycua_agent()
        # run() creates a fresh queue via queue_factory on every call, so the
        # override must be applied inside the factory. Patch the factory to
        # set the response node's retry policy to raise fast (3 attempts)
        # instead of entering the 30-cycle _unbounded_recovery.
        original_factory = agent.loop.queue_factory

        def patched_factory():
            q = original_factory() if original_factory else create_default_queue()
            for n in q.items:
                if n.node_id == "response":
                    n.config.retry_policy = replace(
                        n.config.retry_policy,
                        max_attempts=3,
                        on_retry_exhausted="raise",
                    )
            return q

        agent.loop.queue_factory = patched_factory
        agent._call_llm = AsyncMock(
            side_effect=[
                {"content": ROUTE_PASSTHROUGH, "tool_calls": []},
                *[
                    {
                        "content": "",
                        "tool_calls": None,
                        "usage": None,
                        "finish_reason": "completed",
                        "model": None,
                    }
                    for _ in range(3)
                ],
            ]
        )
        # The SDK stream catches NodeExecutionError and yields an error event.
        result = await agent.run("hello", stream=True)
        with pytest.raises(
            NodeExecutionError, match="Final response must be non-empty"
        ):
            _ = [e async for e in result]
        session = agent.loop.root_session
        # chat_history includes tool_result records (route-tool execution);
        # only assistant records should be retry-type (no empty assistant text).
        assistant_records = [r for r in session.chat_history if r.role == "assistant"]
        assert all(record.record_type == "retry" for record in assistant_records)
        assert session.input_context[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_run_stream_does_not_record_empty_assistant_response(self):
        """Empty streaming responses are not recorded in chat history."""
        from dataclasses import replace

        from tinycua.factory import create_default_queue

        agent = create_tinycua_agent()
        original_factory = agent.loop.queue_factory

        def patched_factory():
            q = original_factory() if original_factory else create_default_queue()
            for n in q.items:
                if n.node_id == "response":
                    n.config.retry_policy = replace(
                        n.config.retry_policy,
                        max_attempts=3,
                        on_retry_exhausted="raise",
                    )
            return q

        agent.loop.queue_factory = patched_factory

        call_count = 0

        async def empty_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {
                    "type": "response.tool_call",
                    "id": "call_route",
                    "function": {
                        "name": "select_query_route",
                        "arguments": '{"route":"passthrough"}',
                    },
                }
                yield {"type": "response.completed", "finish_reason": "completed"}
                return
            yield {"type": "response.completed", "finish_reason": "completed"}

        agent._call_llm = empty_stream
        result = await agent.run("hello", stream=True)
        with pytest.raises(
            NodeExecutionError, match="Final response must be non-empty"
        ):
            _ = [e async for e in result]
        session = agent.loop.root_session
        assistant_records = [r for r in session.chat_history if r.role == "assistant"]
        assert all(record.record_type == "retry" for record in assistant_records)
        assert session.input_context[0]["role"] == "user"
