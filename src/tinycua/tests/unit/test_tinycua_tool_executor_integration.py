"""TinyCUA runtime tool execution uses SDK ToolExecutor."""

from __future__ import annotations

import pytest

from tinycua.config.types import LLMResult, Tool
from tinycua.config.node_config import create_node_config
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode, TinyCUATaskAssessorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.task import TaskStateStore
from tinycua.tools.task_tools import (
    TaskCreateTool,
    TaskDecomposeTool,
    TaskShrinkTool,
    TaskUpdateTool,
)
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
async def test_analyzer_direct_description_update_resolves_selected_target() -> None:
    """A meaningful direct edit resolves a finding without a planning note."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Backend", parent_id=root.task_id)
    finding = {
        "task_id": target.task_id,
        "finding": "The persistence boundary is missing.",
        "assessment_id": "assessment-update",
    }
    target.metadata["planning_finding"] = finding
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Clarify the selected target.",
        payload={
            "decision": "analyze",
            "selected_task_ids": [target.task_id],
            "findings": [finding],
        },
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(analyzer, handoff)
    update = TaskUpdateTool()
    update.bind_task_store(store)
    update.bind_source_node("task_analyzer")

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_update",
                    "arguments": {
                        "task_id": target.task_id,
                        "description": "Persist blocks in SQLite across restarts.",
                    },
                }
            }
        ],
        [update],
        analyzer,
    )
    analyzer.progress.mark_tool_called("task_update", success=True)

    assert results[0]["output"]["success"] is True
    assert handoff.payload["_resolved_task_ids"] == [target.task_id]
    assert loop._can_terminate(analyzer) is True


@pytest.mark.asyncio
async def test_analyzer_delete_resolves_selected_ancestor_from_pre_mutation_tree() -> (
    None
):
    """Deleting a redundant descendant resolves its selected ancestor finding."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Frontend", parent_id=root.task_id)
    redundant = store.create_task("Duplicate styling", parent_id=target.task_id)
    finding = {
        "task_id": target.task_id,
        "finding": "The subtree contains duplicate work.",
        "assessment_id": "assessment-delete",
    }
    target.metadata["planning_finding"] = finding
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Remove the duplicate work.",
        payload={
            "decision": "analyze",
            "selected_task_ids": [target.task_id],
            "findings": [finding],
        },
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(analyzer, handoff)
    shrink = TaskShrinkTool()
    shrink.bind_task_store(store)

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_shrink",
                    "arguments": {
                        "action": "delete",
                        "task_id": redundant.task_id,
                        "rationale": "This duplicates the parent outcome.",
                    },
                }
            }
        ],
        [shrink],
        analyzer,
    )
    analyzer.progress.mark_tool_called("task_shrink", success=True)

    assert results[0]["output"]["success"] is True
    assert redundant.task_id not in store.tasks
    assert handoff.payload["_resolved_task_ids"] == [target.task_id]
    assert loop._can_terminate(analyzer) is True


@pytest.mark.asyncio
async def test_analyzer_unrelated_create_does_not_resolve_active_target() -> None:
    """Creating under another parent cannot resolve the active selected task."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Selected", parent_id=root.task_id)
    other = store.create_task("Other", parent_id=root.task_id)
    store.active_task_id = target.task_id
    finding = {
        "task_id": target.task_id,
        "finding": "Clarify the selected outcome.",
        "assessment_id": "assessment-create",
    }
    analyzer = TinyCUATaskAnalyzerNode(
        "task_analyzer",
        create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Resolve the selected target.",
        payload={
            "decision": "analyze",
            "selected_task_ids": [target.task_id],
            "findings": [finding],
        },
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(analyzer, handoff)
    create = TaskCreateTool()
    create.bind_task_store(store)

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_create",
                    "arguments": {
                        "title": "Other child",
                        "parent_id": other.task_id,
                    },
                }
            }
        ],
        [create],
        analyzer,
    )

    assert results[0]["output"]["success"] is True
    assert handoff.payload.get("_resolved_task_ids", []) == []


@pytest.mark.asyncio
async def test_analyzer_malformed_task_reference_returns_tool_error() -> None:
    """Impact capture leaves malformed arguments to structured tool validation."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Selected", parent_id=root.task_id)
    finding = {
        "task_id": target.task_id,
        "finding": "Split this task.",
        "assessment_id": "assessment-malformed",
    }
    analyzer = TinyCUATaskAnalyzerNode(
        "task_analyzer",
        create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(
        analyzer,
        NodeHandoff(
            source_node="task_assessor",
            target_node="task_analyzer",
            instruction="Resolve the selected target.",
            payload={
                "decision": "analyze",
                "selected_task_ids": [target.task_id],
                "findings": [finding],
            },
        ),
    )
    decompose = TaskDecomposeTool()
    decompose.bind_task_store(store)

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": {"task_id": {"bad": "reference"}, "subtasks": []},
                }
            }
        ],
        [decompose],
        analyzer,
    )

    assert "error" in results[0]


@pytest.mark.asyncio
async def test_analyzer_null_task_reference_resolves_active_target() -> None:
    """An explicit null update target retains active-task semantics."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Selected", parent_id=root.task_id)
    store.active_task_id = target.task_id
    finding = {
        "task_id": target.task_id,
        "finding": "Clarify the selected outcome.",
        "assessment_id": "assessment-null",
    }
    analyzer = TinyCUATaskAnalyzerNode(
        "task_analyzer",
        create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    handoff = NodeHandoff(
        source_node="task_assessor",
        target_node="task_analyzer",
        instruction="Resolve the selected target.",
        payload={
            "decision": "analyze",
            "selected_task_ids": [target.task_id],
            "findings": [finding],
        },
    )
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(analyzer, handoff)
    update = TaskUpdateTool()
    update.bind_task_store(store)
    update.bind_source_node("task_analyzer")

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_update",
                    "arguments": {
                        "task_id": None,
                        "description": "A focused outcome with observable evidence.",
                    },
                }
            }
        ],
        [update],
        analyzer,
    )

    assert results[0]["output"]["success"] is True
    assert handoff.payload["_resolved_task_ids"] == [target.task_id]


@pytest.mark.asyncio
async def test_analyzer_stops_continuation_when_commit_makes_no_target_progress() -> (
    None
):
    """An unrelated commit cannot trigger six more analyzer model calls."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    target = store.create_task("Target", parent_id=root.task_id)
    unrelated = store.create_task("Unrelated", parent_id=root.task_id)
    finding = {
        "task_id": target.task_id,
        "finding": "Clarify this target.",
        "assessment_id": "assessment-no-progress",
    }
    target.metadata["planning_finding"] = finding
    config = create_node_config("task_analyzer", mode="effort_loop_decomposition")
    config.retry_policy.max_attempts = 1
    analyzer = TinyCUATaskAnalyzerNode("task_analyzer", config)
    analyzer.ensure_session(loop.root_session)
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(
        analyzer,
        NodeHandoff(
            source_node="task_assessor",
            target_node="task_analyzer",
            instruction="Resolve the target.",
            payload={
                "decision": "analyze",
                "selected_task_ids": [target.task_id],
                "findings": [finding],
            },
        ),
    )
    update = TaskUpdateTool()
    update.bind_task_store(store)
    update.bind_source_node("task_analyzer")
    agent = Agent(llm_model=LanguageModel())
    calls = 0

    async def call_llm(messages, tools, stream=False):  # noqa: ANN001, ARG001
        nonlocal calls
        calls += 1
        return {
            "content": "",
            "tool_calls": [
                {
                    "id": f"call-{calls}",
                    "type": "function",
                    "function": {
                        "name": "task_update",
                        "arguments": {
                            "task_id": unrelated.task_id,
                            "planning_note": "Unrelated context.",
                        },
                    },
                }
            ],
        }

    agent._call_llm = call_llm  # type: ignore[method-assign]

    _result, _attempt, validation = await loop._call_node_with_retry(
        analyzer,
        agent,
        [{"role": "user", "content": "Refine the roadmap."}],
        [update],
    )

    assert validation.is_valid is False
    assert calls == 1


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


@pytest.mark.asyncio
async def test_analyzer_multi_commit_freezes_numeric_task_references() -> None:
    """Numbered targets retain their original identity across a mutation batch."""
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

    results = await loop._execute_tool_calls(
        Agent(llm_model=LanguageModel()),
        [
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": {"task_id": "1", "subtasks": ["First child"]},
                }
            },
            {
                "function": {
                    "name": "task_decompose",
                    "arguments": {"task_id": "2", "subtasks": ["Second child"]},
                }
            },
        ],
        [decompose],
        analyzer,
    )

    assert [result["output"]["task_id"] for result in results] == [
        first.task_id,
        second.task_id,
    ]
    assert [store.get_task(task_id).title for task_id in first.children] == [
        "First child"
    ]
    assert [store.get_task(task_id).title for task_id in second.children] == [
        "Second child"
    ]


def test_analyzer_commit_directive_requires_all_selected_targets() -> None:
    """An unresolved assessor handoff permits commits beyond the first call."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    targets = [
        store.create_task("First", parent_id=root.task_id),
        store.create_task("Second", parent_id=root.task_id),
    ]
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=create_node_config("task_analyzer", mode="effort_loop_decomposition"),
    )
    analyzer.progress.advance_lifecycle(LifecyclePhase.COMMIT)
    loop.queue = NodeQueue([analyzer])
    loop.queue.set_input(
        analyzer,
        NodeHandoff(
            source_node="task_assessor",
            target_node="task_analyzer",
            instruction="Resolve every selected target.",
            payload={
                "decision": "analyze",
                "selected_task_ids": [target.task_id for target in targets],
                "findings": [],
            },
        ),
    )

    directive = loop._lifecycle_phase_directive(analyzer)

    assert "all assessor-selected targets" in directive
    assert "exactly one" not in directive
    assert "no further tool calls" not in directive
