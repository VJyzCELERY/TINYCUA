"""Focused lifecycle tests for direct ACTION commits and COMMIT fallback."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import Tool
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskResult
from tinycua.tools.task_tools import TaskResultUpdateTool
from tinycua_sdk import Agent, LanguageModel


def _tool_call(name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    return {
        "id": f"call-{name}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": (
                json.dumps(arguments) if isinstance(arguments, dict) else arguments
            ),
        },
    }


class _SequenceLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        self.calls.append(
            {"messages": messages, "tool_names": [tool.name for tool in tools]}
        )
        return self.responses[len(self.calls) - 1]


class _ActionTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="write_file")
        self.paths: list[str] = []

    def __call__(self, path: str) -> dict[str, Any]:
        self.paths.append(path)
        return {"success": True, "path": path}


class _FailOnceResultTool(TaskResultUpdateTool):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def __call__(self, **arguments: Any) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            return {"success": False, "error": "temporary failure"}
        return super().__call__(**arguments)


def _executor_setup(
    *, result_tool: TaskResultUpdateTool | None = None
) -> tuple[TinyCUALoop, TinyCUATaskExecutorNode, str]:
    config = create_node_config("task_executor")
    if result_tool is not None:
        config.tool_policy.node_tools = [result_tool]
    node = TinyCUATaskExecutorNode(node_id="task_executor", config=config)
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    task = loop.root_session.task_store.create_task("Implement focused change")
    return loop, node, task.task_id


@pytest.mark.asyncio
@pytest.mark.parametrize("streamed", [False, True])
async def test_direct_action_commit_completes_without_commit_llm_call(
    streamed: bool,
) -> None:
    loop, node, task_id = _executor_setup()
    action = _ActionTool()
    llm = _SequenceLLM(
        [
            {
                "content": "Implemented and verified the change.",
                "tool_calls": [
                    _tool_call("write_file", {"path": "first.py"}),
                    _tool_call(
                        "task_result_update",
                        {"content": "Implemented and verified.", "success": True},
                    ),
                    _tool_call("write_file", {"path": "must-not-run.py"}),
                ],
            }
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    if streamed:
        async for _ in loop._stream_node_events(node, agent, [action], None, None):
            pass
    else:
        await loop._execute_node(node, agent, [action])

    assert len(llm.calls) == 1
    assert set(llm.calls[0]["tool_names"]) >= {"write_file", "task_result_update"}
    assert "terminate" not in llm.calls[0]["tool_names"]
    assert action.paths == ["first.py"]
    assert loop.root_session.task_store.get_task(task_id).result is not None


@pytest.mark.asyncio
async def test_action_summary_falls_back_to_commit_only_phase() -> None:
    loop, node, _ = _executor_setup()
    llm = _SequenceLLM(
        [
            {"content": "Action Summary: verified existing work.", "tool_calls": []},
            {
                "content": "",
                "tool_calls": [
                    _tool_call(
                        "task_result_update",
                        {"content": "Verified existing work.", "success": True},
                    )
                ],
            },
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [_ActionTool()])

    assert len(llm.calls) == 2
    assert set(llm.calls[0]["tool_names"]) >= {"write_file", "task_result_update"}
    assert set(llm.calls[1]["tool_names"]) == {"task_result_update"}
    assert "Action Summary: verified existing work." in json.dumps(
        llm.calls[1]["messages"]
    )


@pytest.mark.asyncio
async def test_action_tools_remain_available_across_continuations() -> None:
    loop, node, _ = _executor_setup()
    action = _ActionTool()
    llm = _SequenceLLM(
        [
            {
                "content": "Inspected the first artifact.",
                "tool_calls": [_tool_call("write_file", {"path": "first.py"})],
            },
            {
                "content": "Completed the second artifact.",
                "tool_calls": [
                    _tool_call("write_file", {"path": "second.py"}),
                    _tool_call(
                        "task_result_update",
                        {"content": "Implemented both artifacts.", "success": True},
                    ),
                ],
            },
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [action])

    assert action.paths == ["first.py", "second.py"]
    assert len(llm.calls) == 2
    assert all("write_file" in call["tool_names"] for call in llm.calls)


@pytest.mark.asyncio
async def test_successful_commit_first_suppresses_later_action_in_mixed_batch() -> None:
    loop, node, _ = _executor_setup()
    action = _ActionTool()
    llm = _SequenceLLM(
        [
            {
                "content": "Verified existing work.",
                "tool_calls": [
                    _tool_call(
                        "task_result_update",
                        {"content": "Existing work is valid.", "success": True},
                    ),
                    _tool_call("write_file", {"path": "must-not-run.py"}),
                ],
            }
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [action])

    assert len(llm.calls) == 1
    assert action.paths == []


@pytest.mark.asyncio
async def test_failed_action_commit_retries_commit_without_reopening_action() -> None:
    result_tool = _FailOnceResultTool()
    loop, node, _ = _executor_setup(result_tool=result_tool)
    action = _ActionTool()
    commit = _tool_call(
        "task_result_update",
        {"content": "Implemented and verified.", "success": True},
    )
    llm = _SequenceLLM(
        [
            {
                "content": "Action Summary: implementation complete.",
                "tool_calls": [
                    _tool_call("write_file", {"path": "done.py"}),
                    commit,
                    _tool_call("write_file", {"path": "must-not-run.py"}),
                ],
            },
            {"content": "", "tool_calls": [commit]},
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [action])

    assert len(llm.calls) == 2
    assert set(llm.calls[1]["tool_names"]) == {"task_result_update"}
    assert action.paths == ["done.py"]
    assert result_tool.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["malformed", "denied"])
async def test_invalid_action_commit_enters_commit_only_retry(failure: str) -> None:
    loop, node, _ = _executor_setup()
    action = _ActionTool()
    valid_commit = _tool_call(
        "task_result_update",
        {"content": "Implemented and verified.", "success": True},
    )
    first_commit = (
        _tool_call("task_result_update", "{")
        if failure == "malformed"
        else valid_commit
    )
    responses = [
        {
            "content": "Action Summary: implementation complete.",
            "tool_calls": [first_commit, _tool_call("write_file", {"path": "late.py"})],
        },
        {"content": "", "tool_calls": [valid_commit]},
    ]
    calls: list[list[str]] = []
    agent = Agent(llm_model=LanguageModel())
    if failure == "denied":
        agent.tool_permissions["task_result_update"] = "deny"

    async def llm_call(
        _messages: list[dict[str, Any]],
        tools: list[Tool],
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        del stream
        calls.append([tool.name for tool in tools])
        if len(calls) == 2:
            agent.tool_permissions["task_result_update"] = "allow"
        return responses[len(calls) - 1]

    agent._call_llm = llm_call  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [action])

    assert set(calls[1]) == {"task_result_update"}
    assert action.paths == []


@pytest.mark.asyncio
async def test_reviewer_decision_stays_staged_until_validation_then_commits_once() -> (
    None
):
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    store = loop.root_session.task_store
    task = store.create_task("Review completed work")
    store.record_result(task.task_id, TaskResult(content="done", success=True))
    llm = _SequenceLLM(
        [
            {
                "content": "",
                "tool_calls": [_tool_call("task_inspect", {})],
            },
            {
                "content": "approved",
                "tool_calls": [
                    _tool_call(
                        "task_review_decision",
                        {"decision": "approved", "rationale": ""},
                    )
                ],
            },
            {
                "content": "approved",
                "tool_calls": [
                    _tool_call(
                        "task_review_decision",
                        {"decision": "approved", "rationale": "Verified outcome."},
                    )
                ],
            },
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [])

    assert len(llm.calls) == 3
    assert set(llm.calls[1]["tool_names"]) == {
        "task_review_decision",
        "json_draft_create",
        "json_draft_commit",
    }
    assert task.reviewer_decisions == [
        {
            "event_id": "review-1",
            "review_summary": "Verified outcome.",
            "decision": "approved",
            "rationale": "Verified outcome.",
            "new_findings": [],
            "finding_updates": [],
            "metadata": {"context_updates": []},
        }
    ]
    assert task.task_id not in store._staged_reviewer_decisions


@pytest.mark.asyncio
async def test_analyzer_accepts_first_successful_mutation_and_suppresses_rest() -> None:
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer"),
    )
    loop = TinyCUALoop(queue=NodeQueue(items=[node]))
    store = loop.root_session.task_store
    root = store.create_task("Root")
    child = store.create_task("Existing child", parent_id=root.task_id)
    llm = _SequenceLLM(
        [
            {
                "content": "The existing child only needs clarification.",
                "tool_calls": [
                    _tool_call(
                        "task_update",
                        {"task_id": child.task_id, "description": "Clarified scope."},
                    ),
                    _tool_call(
                        "task_decompose",
                        {"task_id": child.task_id, "subtasks": ["Must not exist"]},
                    ),
                ],
            }
        ]
    )
    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = llm  # type: ignore[method-assign]

    await loop._execute_node(node, agent, [])

    assert len(llm.calls) == 1
    assert child.description == "Clarified scope."
    assert child.children == []


def test_action_exposes_owned_commit_tools_but_never_terminate() -> None:
    loop, node, _ = _executor_setup()
    tools = [
        Tool(name="write_file"),
        Tool(name="task_result_update"),
        Tool(name="task_review_decision"),
        Tool(name="terminate"),
    ]

    assert [
        tool.name for tool in loop._phase_tools(node, tools, LifecyclePhase.ACTION)
    ] == ["write_file", "task_result_update"]
