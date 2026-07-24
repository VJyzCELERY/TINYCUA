"""Integration tests for lazy retry through _execute_node (FR-087..FR-093).

End-to-end: a node's first LLM response completes without calling the required
state tool. With recovery_strategy="markdown_synthesis", the runtime makes one
no-tools non-streaming continuation, parses the markdown, synthesizes the state
tool call, and completes action, commit, and terminate phases in 3 LLM calls.

Written BEFORE implementation (TDD RED phase).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskStatus
from tinycua.tools.task_tools import TaskResultUpdateTool


_EXECUTOR_VALID_MARKDOWN = (
    "# Status : completed\n"
    "# Summary\n"
    "Implemented and verified the feature.\n"
    "# Task ID\n"
    "{task_id}\n"
)


class _SequenceLLM:
    """Mock LLM returning a queued sequence of responses."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def __call__(self, messages: list[dict[str, Any]], tools: list[Any], stream: bool = False, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        idx = min(self.call_count, len(self._responses) - 1)
        self.call_count += 1
        self.calls.append({"messages": messages, "tools": tools, "stream": stream})
        return self._responses[idx]


@pytest.mark.asyncio
async def test_executor_terminates_with_lazy_retry():
    """Attempt 1 fails (no tool call), lazy synthesizes task_result_update, then
    the lifecycle completes action, commit, and terminate phases."""
    loop = TinyCUALoop()
    loop.session_config = SessionConfig(recovery_strategy="markdown_synthesis")

    store = loop.root_session.task_store
    root = store.create_task("Build feature")
    store.active_task_id = root.task_id
    store.transition(root.task_id, TaskStatus.IN_PROGRESS)

    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)

    # Response 1: no tool call (validation fails: missing task_result_update).
    # Response 2: valid lazy markdown with the active task_id.
    # (Any further calls would be the standard retry path; we don't expect
    # to reach them because the lifecycle completes after the terminate phase.)
    lazy_markdown = _EXECUTOR_VALID_MARKDOWN.format(task_id=root.task_id)
    llm = _SequenceLLM([
        {"role": "assistant", "content": "I'm done with the task.", "tool_calls": []},
        {"role": "assistant", "content": lazy_markdown},
    ])

    agent = MagicMock()
    agent.tool_permissions = {}
    agent._call_llm = llm

    # _execute_node runs the full lifecycle: retry → lazy commit report → terminate.
    content, tool_calls = await loop._execute_node(node, agent, tools=[TaskResultUpdateTool()])

    # ACTION, COMMIT, and TERMINATE each require a focused LLM call.
    assert llm.call_count == 3, f"Expected 3 LLM calls, got {llm.call_count}"
    # The synthesized commit report is immediately visible to the reviewer.
    task = store.tasks[root.task_id]
    assert task.result is not None, "task_result_update should persist its report"
    assert task.result.success is True
    # The node produced output (content or tool calls).
    assert content or tool_calls


@pytest.mark.asyncio
async def test_standard_mode_does_not_use_lazy_retry():
    """Default recovery_strategy='standard' → lazy never called; behavior unchanged."""
    loop = TinyCUALoop()
    loop.session_config = SessionConfig(recovery_strategy="standard")
    assert loop.session_config.recovery_strategy == "standard"

    store = loop.root_session.task_store
    root = store.create_task("Build feature")
    store.active_task_id = root.task_id
    store.transition(root.task_id, TaskStatus.IN_PROGRESS)

    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(loop.root_session)

    # In standard mode, the LLM keeps failing the tool call. Use a small
    # max_attempts to keep the test fast.
    from dataclasses import replace
    node.config.retry_policy = replace(node.config.retry_policy, max_attempts=2)

    # LLM always returns a no-tool-call response.
    def always_fail(messages, tools, stream=False, **kwargs):  # noqa: ARG001
        return {"role": "assistant", "content": "no tool call", "tool_calls": []}
    agent = MagicMock()
    agent.tool_permissions = {}
    agent._call_llm = always_fail

    from tinycua.loops.node import NodeExecutionError

    with pytest.raises(NodeExecutionError):
        await loop._execute_node(node, agent, tools=[TaskResultUpdateTool()])

    assert store.tasks[root.task_id].status != TaskStatus.COMPLETED
