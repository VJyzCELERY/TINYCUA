"""Factory function for creating TinyCUA agents."""

from __future__ import annotations

from typing import Any

from tinycua_sdk.agent import Agent

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import NativeToolPolicy, SessionConfig
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session

_TINYCUA_DEFAULT_TEMPERATURE = 0.6


def create_default_queue(session_config: SessionConfig | None = None) -> NodeQueue:
    """Create the default TinyCUA queue beginning at QueryAnalyst."""
    base_metadata = {"session_config": session_config} if session_config else {}
    query_analyst = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    query_analyst.config.metadata.update(base_metadata)
    response_node = ResponseNode(config=create_node_config("response"))
    response_node.config.metadata.update(base_metadata)
    return NodeQueue(items=[query_analyst, response_node])


def create_tinycua_agent(
    session: Session | None = None,
    session_config: SessionConfig | None = None,
    enable_native_tools: bool = True,
    native_tool_policy: NativeToolPolicy | None = None,
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
        enable_native_tools: When True, attach native file, shell, Python,
            fetch, and SearXNG web search tools to the SDK Agent. Defaults to
            True because TinyCUA's prototype runtime is actionable by default.
        native_tool_policy: Optional allowlist policy for native tools.
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
    effective_session_config = session_config or session.session_config
    if effective_session_config is not None:
        session.session_config = effective_session_config
    if enable_native_tools:
        existing_tools = list(agent_kwargs.pop("tools", []) or [])
        native_tools = _native_tools(native_tool_policy)
        existing_names = {tool.name for tool in existing_tools}
        existing_tools.extend(tool for tool in native_tools if tool.name not in existing_names)
        agent_kwargs["tools"] = existing_tools
    _apply_tinycua_model_defaults(agent_kwargs)
    queue = create_default_queue(effective_session_config)
    terminal_node = queue.items[-1]
    loop = TinyCUALoop(
        root_session=session,
        queue=queue,
        session_config=effective_session_config,
        default_terminal_node=terminal_node,
        queue_factory=lambda: create_default_queue(effective_session_config),
    )
    return Agent(loop=loop, **agent_kwargs)


def _apply_tinycua_model_defaults(agent_kwargs: dict[str, Any]) -> None:
    """Apply TinyCUA runtime defaults without changing SDK global defaults."""
    model = agent_kwargs.get("llm_model")
    if model is None:
        return
    fields_set = getattr(model, "model_fields_set", set())
    if "temperature" in fields_set:
        return
    copier = getattr(model, "model_copy", None)
    if callable(copier):
        agent_kwargs["llm_model"] = copier(
            update={"temperature": _TINYCUA_DEFAULT_TEMPERATURE}
        )


def _native_tools(policy: NativeToolPolicy | None = None) -> list[Any]:
    """Return optional native tools filtered by policy."""
    from tinycua.agent.tools.native import (
        edit_file,
        fetch_url,
        list_files,
        read_file,
        run_python,
        run_shell,
        web_search,
        write_file,
    )

    tool_policy = policy or NativeToolPolicy()
    tools = [
        read_file,
        write_file,
        edit_file,
        list_files,
        run_shell,
        run_python,
        fetch_url,
        web_search,
    ]
    return [tool for tool in tools if tool_policy.permits(tool.name)]
