"""Factory function for creating TinyCUA agents."""

from __future__ import annotations

from typing import Any

from tinycua_sdk.agent import Agent

from tinycua.config.session_config import SessionConfig
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


def create_tinycua_agent(
    session: Session | None = None,
    session_config: SessionConfig | None = None,
    **agent_kwargs: Any,
) -> Agent:
    """Create a TinyCUA agent backed by the SDK Agent and TinyCUALoop.

    Constructs an SDK Agent with a TinyCUALoop attached, enabling the
    full TinyCUA node-based execution flow without SDK API modifications.

    Args:
        session: Optional pre-existing session. If None, a new root session
            is created automatically.
        session_config: Optional session configuration. Applied to the
            session and stored on the loop.
        **agent_kwargs: Additional keyword arguments passed through to the
            SDK Agent constructor (e.g., name, instructions, tools).

    Returns:
        An SDK Agent instance with TinyCUALoop attached as its loop.

    Example::

        agent = create_tinycua_agent(
            name="my-agent",
            instructions="Be helpful",
            session_config=SessionConfig(max_context_messages=50),
        )
        result = await agent.run("hello")
    """
    if session is None:
        session = Session()
    if session_config is not None:
        session.session_config = session_config
    terminal_node = ResponseNode()
    loop = TinyCUALoop(
        root_session=session,
        session_config=session_config,
        default_terminal_node=terminal_node,
    )
    return Agent(loop=loop, **agent_kwargs)
