"""Contracts for actionable TinyCUA traceability."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskStateStore, TaskStatus


async def test_streaming_emits_node_prefixed_transcript_events() -> None:
    """Streaming should expose readable [Node] deltas alongside raw events."""
    terminal = ResponseNode(config=NodeConfigBase())
    loop = TinyCUALoop(queue=NodeQueue(items=[terminal]))
    agent = MagicMock()

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        yield {"type": "response.output_text.delta", "delta": "Hello"}
        yield {"type": "response.output_text.delta", "delta": " world"}
        yield {"type": "response.completed", "finish_reason": "completed"}

    agent._call_llm = call_llm

    stream = await loop.run(
        agent,
        [{"role": "user", "content": "Say hello."}],
        tools=[],
        stream=True,
    )
    events = [event async for event in stream]

    transcript_events = [event for event in events if event.get("type") == "transcript.delta"]
    assert transcript_events
    assert transcript_events[0]["delta"].startswith("[Response]")
    assert any(event["node_label"] == "Response" for event in loop.get_transcript_events())


def test_task_tree_renderer_shows_nested_hierarchy() -> None:
    """Task trees should have a readable text hierarchy for notebook/CLI users."""
    store = TaskStateStore()
    root = store.create_task("Build note app")
    backend = store.create_task("Create backend", parent_id=root.task_id)
    store.create_task("Write API", parent_id=backend.task_id)
    store.create_task("Create frontend", parent_id=root.task_id)
    store.transition(root.task_id, TaskStatus.IN_PROGRESS)

    rendered = TinyCUALoop().render_task_tree(store)

    assert "Task [in_progress] Build note app" in rendered
    assert "|- Task [pending] Create backend" in rendered
    assert "|  |- Task [pending] Write API" in rendered
    assert "|- Task [pending] Create frontend" in rendered


def test_default_agent_exposes_workspace_action_and_web_search_tools(tmp_path: Path) -> None:
    """TinyCUA agents should be actionable by default, not planner-only."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))

    tool_names = {tool.name for tool in agent.tools}

    assert {"write_file", "read_file", "run_shell", "run_python", "web_search"} <= tool_names


async def test_reusing_session_preserves_in_memory_context(tmp_path: Path) -> None:
    """A provided Session can continue across agent instances/runs in memory."""
    from tinycua.models.session import Session

    session = Session()
    config = SessionConfig(workspace_dir=tmp_path)
    first = create_tinycua_agent(session=session, session_config=config)
    second = create_tinycua_agent(session=session, session_config=config)

    async def call_llm(messages, tools, stream: bool = False):  # noqa: ANN001, ARG001
        return {"content": "remembered", "tool_calls": []}

    first._call_llm = call_llm  # type: ignore[method-assign]
    second._call_llm = call_llm  # type: ignore[method-assign]

    await first.run("Remember this session.")
    session.todo.append({"content": "continue work", "status": "pending"})
    session.task_store.create_task("Continue app")
    await second.run("Continue.")

    assert second.loop.root_session is session
    assert session.todo == [{"content": "continue work", "status": "pending"}]
    assert session.task_store.root_task_id is not None
    assert session.input_context[-1]["content"] == "Continue."
