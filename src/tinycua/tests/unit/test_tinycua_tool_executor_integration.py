"""TinyCUA runtime tool execution uses SDK ToolExecutor."""

from __future__ import annotations

import pytest

from tinycua.config.types import Tool
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskStateStore
from tinycua.tools.task_tools import TaskDecomposeTool
from tinycua_sdk import Agent, LanguageModel


class DeniedProbeTool(Tool):
    """Tool that records whether the underlying callable ran."""

    def __init__(self) -> None:
        super().__init__(name="denied_probe")
        self.invoked = False

    def __call__(self) -> dict[str, bool]:
        """Return success if invoked."""
        self.invoked = True
        return {"invoked": True}


@pytest.mark.asyncio
async def test_execute_tool_calls_uses_sdk_denial() -> None:
    """Denied SDK permissions prevent TinyCUA from invoking the tool."""
    loop = TinyCUALoop()
    tool = DeniedProbeTool()
    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"denied_probe": "deny"},
    )

    results = await loop._execute_tool_calls(
        agent,
        [{"type": "function", "function": {"name": "denied_probe", "arguments": "{}"}}],
        [tool],
    )

    assert tool.invoked is False
    assert results[0]["allowed"] is True
    assert "denied" in results[0]["output"]["error"]


@pytest.mark.asyncio
async def test_raw_llm_decomposition_calls_are_incremental_and_atomic() -> None:
    """Malformed or invalid raw calls leave task state intact for correction."""
    loop = TinyCUALoop()
    agent = Agent(llm_model=LanguageModel())
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["First", "Second"])
    tool = TaskDecomposeTool()
    tool.bind_task_store(store)

    first = await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "task_decompose", "arguments": (
            f'{{"task_id":"{root.task_id}","subtasks":['
            '{"title":"First work","clause_ids":["acceptance-1"]}]}'
        )}}],
        [tool],
    )
    invalid = await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "task_decompose", "arguments": "{"}}],
        [tool],
    )
    unknown_clause = await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "task_decompose", "arguments": (
            f'{{"task_id":"{root.task_id}","subtasks":['
            '{"title":"Invalid work","clause_ids":["acceptance-3"]}]}'
        )}}],
        [tool],
    )
    second = await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "task_decompose", "arguments": (
            f'{{"task_id":"{root.task_id}","subtasks":['
            '{"title":"Second work","clause_ids":["acceptance-2"]}]}'
        )}}],
        [tool],
    )

    assert first[0]["output"]["success"] is True
    assert "error" in invalid[0]
    assert unknown_clause[0]["output"]["success"] is False
    assert second[0]["output"]["success"] is True
    assert [store.get_task(task_id).title for task_id in root.children] == [
        "First work",
        "Second work",
    ]
