"""Tests for TinyCUALoop."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua_sdk.agent import BaseLoop
from tinycua.config.session_config import SessionConfig
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


def test_tinycua_loop_extends_base_loop():
    """TinyCUALoop is a subclass of SDK BaseLoop."""
    session = Session()
    loop = TinyCUALoop(root_session=session)
    assert isinstance(loop, BaseLoop)


def test_tinycua_loop_creates_session_by_default():
    """TinyCUALoop creates a Session when none provided."""
    loop = TinyCUALoop()
    assert isinstance(loop.root_session, Session)
    assert loop.root_session.session_id is not None


def test_tinycua_loop_uses_provided_session():
    """TinyCUALoop uses the provided session."""
    session = Session()
    loop = TinyCUALoop(root_session=session)
    assert loop.root_session is session


def test_tinycua_loop_has_node_queue():
    """TinyCUALoop creates a NodeQueue by default."""
    loop = TinyCUALoop()
    assert isinstance(loop.queue, NodeQueue)
    assert loop.queue.is_empty() is True


def test_tinycua_loop_stores_session_config():
    """TinyCUALoop stores session_config; factory applies it to session."""
    config = SessionConfig(max_context_messages=50)
    loop = TinyCUALoop(session_config=config)
    assert loop.session_config is config
    # Config application to root_session is the factory's responsibility
    assert loop.root_session.session_config is None


def test_tinycua_loop_default_max_iterations():
    """TinyCUALoop defaults to 50 max iterations."""
    loop = TinyCUALoop()
    assert loop.max_iterations == 50


def test_tinycua_loop_custom_max_iterations():
    """TinyCUALoop accepts custom max_iterations."""
    loop = TinyCUALoop(max_iterations=10)
    assert loop.max_iterations == 10


@pytest.mark.asyncio
async def test_run_records_user_message():
    """run() records user messages in chat_history."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "Hi", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "hello"}]
    await loop.run(agent, messages, tools=[], stream=False)
    user_msgs = [m for m in loop.root_session.chat_history if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_run_records_assistant_response():
    """run() records assistant response in chat_history."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "Hello there", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "hi"}]
    await loop.run(agent, messages, tools=[], stream=False)
    assistant_msgs = [m for m in loop.root_session.chat_history if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == "Hello there"


@pytest.mark.asyncio
async def test_run_calls_build_system_message_with_override():
    """run() passes override_instructions to build_system_message."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
    )
    messages = [{"role": "user", "content": "test"}]
    with pytest.MonkeyPatch.context() as m:
        original_build = loop.build_system_message
        called_with = []
        def spy_build(a, override=None):
            called_with.append(override)
            return original_build(a, override)
        m.setattr(loop, "build_system_message", spy_build)
        await loop.run(agent, messages, tools=[], override_instructions="custom instructions", stream=False)
    assert called_with == ["custom instructions"]


@pytest.mark.asyncio
async def test_run_stream_records_chat_history():
    """run(stream=True) records accumulated content in chat_history."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "You are helpful"
    agent.skills = []

    async def mock_stream(*args, **kwargs):
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = mock_stream
    messages = [{"role": "user", "content": "hi"}]
    result = await loop.run(agent, messages, tools=[], stream=True)
    events = [e async for e in result]
    assert len(events) == 3
    assistant_msgs = [m for m in loop.root_session.chat_history if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == "Hello world"
