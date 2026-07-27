"""TinyCUA runtime tool execution uses SDK ToolExecutor."""

from __future__ import annotations

import pytest

from tinycua.config.types import LLMResult, Tool, ValidationResult
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


@pytest.mark.asyncio
async def test_analyzer_executes_commits_for_all_selected_targets() -> None:
    """One analyzer tool batch resolves every assessor-selected target."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    targets = [
        store.create_task("First target", parent_id=root.task_id),
        store.create_task("Second target", parent_id=root.task_id),
    ]
    findings = []
    for index, target in enumerate(targets, start=1):
        finding = {
            "task_id": target.task_id,
            "finding": "Split this mixed outcome.",
            "assessment_id": f"assessment-{index}",
        }
        target.metadata["planning_finding"] = finding
        findings.append(finding)
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    loop.queue = NodeQueue([analyzer])
    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Resolve every selected target.",
        payload={
            "decision": "analyze",
            "selected_task_ids": [target.task_id for target in targets],
            "findings": findings,
        },
    )
    loop.queue.set_input(analyzer, handoff)
    decompose = TaskDecomposeTool()
    decompose.bind_task_store(store)
    calls = [
        {
            "function": {
                "name": "task_decompose",
                "arguments": {
                    "task_id": target.task_id,
                    "subtasks": [
                        {
                            "title": f"{target.title} child",
                            "description": "A bounded outcome with evidence.",
                        }
                    ],
                },
            }
        }
        for target in targets
    ]

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()), calls, [decompose], analyzer
    )
    analyzer.progress.mark_tool_called("task_decompose", success=True)

    assert len(results) == 2
    assert all(result["output"]["success"] for result in results)
    assert set(handoff.payload["_resolved_task_ids"]) == {
        target.task_id for target in targets
    }
    assert loop._can_terminate(analyzer) is True


@pytest.mark.asyncio
async def test_analyzer_validation_rejects_unresolved_selected_target() -> None:
    """One successful mutation cannot complete a multi-target analyzer handoff."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    findings = [
        {
            "task_id": target.task_id,
            "finding": "Split this mixed outcome.",
            "assessment_id": f"assessment-{index}",
        }
        for index, target in enumerate((first, second), start=1)
    ]
    for target, finding in zip((first, second), findings, strict=True):
        target.metadata["planning_finding"] = finding
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
            instruction="Resolve every selected target.",
            payload={
                "decision": "analyze",
                "selected_task_ids": [first.task_id, second.task_id],
                "findings": findings,
            },
        ),
    )
    decompose = TaskDecomposeTool()
    decompose.bind_task_store(store)
    tool_results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": {
                        "task_id": first.task_id,
                        "subtasks": ["First child"],
                    },
                }
            }
        ],
        [decompose],
        analyzer,
    )
    analyzer.progress.mark_tool_called("task_decompose", success=True)

    validation = loop._validate_node_result(
        analyzer,
        LLMResult(metadata={"tool_results": tool_results}),
    )

    assert validation.is_valid is False
    assert any("every assessor-selected task" in error for error in validation.errors)
