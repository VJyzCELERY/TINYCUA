"""Tests for TinyCUALoop."""

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


def test_tinycua_loop_applies_session_config():
    """TinyCUALoop applies session_config to root_session."""
    config = SessionConfig(max_context_messages=50)
    loop = TinyCUALoop(session_config=config)
    assert loop.session_config is config
    assert loop.root_session.session_config is config


def test_tinycua_loop_default_max_iterations():
    """TinyCUALoop defaults to 50 max iterations."""
    loop = TinyCUALoop()
    assert loop.max_iterations == 50


def test_tinycua_loop_custom_max_iterations():
    """TinyCUALoop accepts custom max_iterations."""
    loop = TinyCUALoop(max_iterations=10)
    assert loop.max_iterations == 10
