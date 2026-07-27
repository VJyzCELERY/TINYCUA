"""TinyCUA runtime tool execution uses SDK ToolExecutor."""

from __future__ import annotations

import pytest

from tinycua.config.types import Tool, ValidationResult
from tinycua.config.node_config import create_node_config
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode, TinyCUATaskAssessorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.task import TaskStateStore
from tinycua.tools.task_tools import TaskDecomposeTool, TaskUpdateTool
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
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": (
                        f'{{"task_id":"{root.task_id}","subtasks":["First work"]}}'
                    ),
                }
            }
        ],
        [tool],
    )
    invalid = await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "task_decompose", "arguments": "{"}}],
        [tool],
    )
    duplicate = await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": (
                        f'{{"task_id":"{root.task_id}","subtasks":["First work"]}}'
                    ),
                }
            }
        ],
        [tool],
    )
    second = await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": (
                        f'{{"task_id":"{root.task_id}","subtasks":["Second work"]}}'
                    ),
                }
            }
        ],
        [tool],
    )

    assert first[0]["output"]["success"] is True
    assert "error" in invalid[0]
    assert duplicate[0]["output"]["success"] is False
    assert second[0]["output"]["success"] is True
    assert [store.get_task(task_id).title for task_id in root.children] == [
        "First work",
        "Second work",
    ]


@pytest.mark.asyncio
async def test_analyzer_must_resolve_each_selected_target_locally() -> None:
    """An unrelated mutation cannot acknowledge a blocking planning finding."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Target", parent_id=root.task_id)
    unrelated = store.create_task("Unrelated", parent_id=root.task_id)
    target.metadata["planning_finding"] = {
        "assessment_id": "assessment-1",
        "finding": "Split the distinct concerns.",
    }
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(
        analyzer,
        NodeHandoff(
            source_node="task_assessor",
            target_node="task_analyzer",
            instruction="Resolve the finding.",
            payload={
                "decision": "analyze",
                "selected_task_ids": [target.task_id],
                "findings": [
                    {
                        "task_id": target.task_id,
                        "finding": "Split the distinct concerns.",
                        "assessment_id": "assessment-1",
                    }
                ],
            },
        ),
    )
    update = TaskUpdateTool()
    update.bind_task_store(store)
    update.bind_source_node("task_analyzer")
    agent = Agent(llm_model=LanguageModel())

    await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "task_update",
                    "arguments": {
                        "task_id": unrelated.task_id,
                        "planning_note": "Keep this unrelated task.",
                    },
                }
            }
        ],
        [update],
        analyzer,
    )
    analyzer.progress.mark_tool_called("task_update", success=True)

    assert loop._can_terminate(analyzer) is False
    assert (
        loop._recover_task_analyzer_validation_failure(
            analyzer,
            ValidationResult(is_valid=False, errors=["selected target unresolved"]),
        )
        is False
    )

    await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "task_update",
                    "arguments": {
                        "task_id": target.task_id,
                        "planning_note": "Retain as one task because the seam is shared.",
                    },
                }
            }
        ],
        [update],
        analyzer,
    )

    assert loop._can_terminate(analyzer) is True
    assert target.metadata["planning_resolution"]["assessment_id"] == "assessment-1"
    detail = store.compact_task_detail(target.task_id)
    assert detail["metadata"]["planning_resolution"]["rationale"].startswith("Retain")

    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor", config=create_node_config("task_assessor")
    )
    continuation = assessor.build_continuation(loop.root_session)
    assert "Split the distinct concerns." in continuation
    assert "Retain as one task" in continuation


@pytest.mark.asyncio
async def test_analyzer_structural_change_resolves_selected_local_subtree() -> None:
    """A decomposition on the selected target satisfies accountability."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Target", parent_id=root.task_id)
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(
        analyzer,
        NodeHandoff(
            source_node="task_assessor",
            target_node="task_analyzer",
            instruction="Split the target.",
            payload={
                "decision": "analyze",
                "selected_task_ids": [target.task_id],
                "findings": [
                    {
                        "task_id": target.task_id,
                        "finding": "Two concerns need separate evidence.",
                        "assessment_id": "assessment-2",
                    }
                ],
            },
        ),
    )
    decompose = TaskDecomposeTool()
    decompose.bind_task_store(store)

    await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": {
                        "task_id": target.task_id,
                        "subtasks": [
                            {"title": "First", "description": "First evidence."},
                            {"title": "Second", "description": "Second evidence."},
                        ],
                    },
                }
            }
        ],
        [decompose],
        analyzer,
    )
    analyzer.progress.mark_tool_called("task_decompose", success=True)

    assert loop._can_terminate(analyzer) is True
    assert target.metadata["planning_resolution"]["summary"].startswith(
        "task_decompose"
    )
