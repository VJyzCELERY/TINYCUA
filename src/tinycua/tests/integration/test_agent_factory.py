"""Integration tests for Agent Factory Contract (Milestone 1.1)."""

import pytest
from unittest.mock import AsyncMock
from tinycua_sdk.agent import Agent, BaseLoop
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


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
            return_value={"content": "Hello", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
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
        async def mock_stream(*args, **kwargs):
            yield {"type": "response.output_text.delta", "delta": "Hi"}
            yield {"type": "response.completed", "finish_reason": "completed"}

        agent._call_llm = mock_stream
        result = await agent.run("hello", stream=True)
        assert hasattr(result, '__aiter__')
        events = [e async for e in result]
        assert len(events) > 0
        assert events[0]["type"] == "response.output_text.delta"
        assert events[0]["delta"] == "Hi"
        session = agent.loop.root_session
        assert len(session.chat_history) == 1  # assistant only (user in input_context)
        assert session.chat_history[0]["role"] == "assistant"
        assert session.chat_history[0]["content"] == "Hi"
        assert session.input_context[0]["role"] == "user"
        assert session.input_context[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_run_populates_session_chat_history(self):
        """agent.run() records assistant responses in session chat history.

        User messages are stored in input_context, not chat_history.
        """
        agent = create_tinycua_agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "Hello", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        await agent.run("hello")
        session = agent.loop.root_session
        assert len(session.chat_history) == 1  # assistant only
        assert session.chat_history[0]["role"] == "assistant"
        assert session.chat_history[0]["content"] == "Hello"
        assert session.input_context[0]["role"] == "user"
        assert session.input_context[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_run_does_not_record_empty_assistant_response(self):
        """Empty assistant responses are not recorded in chat history."""
        agent = create_tinycua_agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        await agent.run("hello")
        session = agent.loop.root_session
        assert len(session.chat_history) == 0  # no assistant response recorded
        assert session.input_context[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_run_stream_does_not_record_empty_assistant_response(self):
        """Empty streaming responses are not recorded in chat history."""
        agent = create_tinycua_agent()

        async def empty_stream(*args, **kwargs):
            yield {"type": "response.completed", "finish_reason": "completed"}

        agent._call_llm = empty_stream
        result = await agent.run("hello", stream=True)
        events = [e async for e in result]
        assert len(events) == 1
        session = agent.loop.root_session
        assert len(session.chat_history) == 0  # no assistant response recorded
        assert session.input_context[0]["role"] == "user"
