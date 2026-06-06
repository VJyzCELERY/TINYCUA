"""Tests for create_tinycua_agent factory function."""

from tinycua_sdk.agent import Agent, BaseLoop
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


def test_factory_returns_agent():
    """Factory returns an SDK Agent instance."""
    agent = create_tinycua_agent()
    assert isinstance(agent, Agent)


def test_factory_returns_agent_with_tinycua_loop():
    """Factory returns Agent with TinyCUALoop attached."""
    agent = create_tinycua_agent()
    assert isinstance(agent.loop, TinyCUALoop)
    assert isinstance(agent.loop, BaseLoop)


def test_factory_creates_session_by_default():
    """Factory creates a new root session when none provided."""
    agent = create_tinycua_agent()
    assert isinstance(agent.loop.root_session, Session)
    assert agent.loop.root_session.session_id is not None


def test_factory_uses_provided_session():
    """Factory uses the provided session."""
    session = Session()
    agent = create_tinycua_agent(session=session)
    assert agent.loop.root_session is session


def test_factory_applies_session_config():
    """Factory applies SessionConfig to session and loop."""
    config = SessionConfig(max_context_messages=50)
    agent = create_tinycua_agent(session_config=config)
    assert agent.loop.session_config == config
    assert agent.loop.root_session.session_config == config


def test_factory_passes_agent_kwargs():
    """Factory passes **agent_kwargs to SDK Agent."""
    agent = create_tinycua_agent(name="test-agent", instructions="Be helpful")
    assert agent.name == "test-agent"
    assert agent.instructions == "Be helpful"


def test_factory_default_loop_iterations():
    """Factory creates loop with default 50 max iterations."""
    agent = create_tinycua_agent()
    assert agent.loop.max_iterations == 50
