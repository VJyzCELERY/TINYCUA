"""TaskAnalyzer-owned roadmaps are preserved exactly (runtime invariant).

Spec: ./specs/tinycua-runtime-invariants/spec.md:180-181, 208-210, 246-249, 261-262
Source: src/tinycua/docs/design/loops/task_analyzer.md:23-31,
        src/tinycua/docs/design/models/task.md:10-28,
        src/tinycua/docs/design/tools/task.md:19-28

The runtime MUST NOT truncate, collapse, or rewrite analyzer-provided subtasks.
TaskDecomposeTool is the boundary tool TaskAnalyzer uses; it must preserve every
subtask in order. The TaskStateStore already preserves all subtasks; the cap and
the app/web-ui collapse live in the tool layer and must be removed there.
"""

from __future__ import annotations

import pytest

from tinycua.models.task import TaskStateStore
from tinycua.tools.task_tools import TaskDecomposeTool, TaskInitTool


def _bind(store: TaskStateStore) -> tuple[TaskInitTool, TaskDecomposeTool]:
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    init.bind_task_store(store)
    decompose.bind_task_store(store)
    return init, decompose


def test_task_decompose_preserves_all_25_subtasks_in_order() -> None:
    """Spec: ./spec.md:180, ./spec.md:208-210, ./spec.md:262.

    Source: task_analyzer.md:23-31, models/task.md:10-28, tools/task.md:19-28.
    TaskAnalyzer owns roadmap size; 25 subtasks must survive intact.
    """
    store = TaskStateStore()
    init, decompose = _bind(store)
    root = init("Any complex task")
    subtasks = [f"Task {i}" for i in range(25)]

    result = decompose(root["task_id"], subtasks)

    assert result["success"] is True
    assert len(result["child_task_ids"]) == 25
    assert [store.get_task(cid).title for cid in result["child_task_ids"]] == subtasks


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 10, 50, 100])
def test_task_decompose_preserves_arbitrary_subtask_counts(count: int) -> None:
    """Spec: ./spec.md:208-210, ./spec.md:246-249.

    Source: task_analyzer.md:23-31, models/task.md:10-28.
    No hard cap may truncate analyzer-created subtasks.
    """
    store = TaskStateStore()
    init, decompose = _bind(store)
    root = init("Root")
    subtasks = [f"S{i}" for i in range(count)]

    result = decompose(root["task_id"], subtasks)

    assert result["success"] is True
    assert len(result["child_task_ids"]) == count


def test_task_decompose_does_not_collapse_app_web_ui_into_one_vertical_slice() -> None:
    """Spec: ./spec.md:29-42, ./spec.md:246-249, ./spec.md:261.

    Source: task_analyzer.md:6-17, task_analyzer.md:23-31.
    The app/web-ui collapse heuristic (`_one_shot_app_subtasks`) is forbidden.
    """
    store = TaskStateStore()
    init, decompose = _bind(store)
    root = init("Build a note taking app with web UI")
    subtasks = ["backend", "frontend", "api layer", "data model"]

    result = decompose(root["task_id"], subtasks)

    assert result["success"] is True
    assert len(result["child_task_ids"]) == 4
    titles = [store.get_task(cid).title for cid in result["child_task_ids"]]
    assert titles == subtasks
    assert not any("vertical-slice" in t.lower() for t in titles)


def test_task_decompose_schema_has_no_maxitems_cap() -> None:
    """Spec: ./spec.md:246-249, ./spec.md:262.

    Source: tools/task.md:19-28.
    The tool JSON schema must not advertise a hard maxItems to the LLM.
    """
    decompose = TaskDecomposeTool()
    subtasks_prop = decompose.parameters["properties"]["subtasks"]
    assert "maxItems" not in subtasks_prop, (
        "task_decompose schema advertises a maxItems cap; remove it."
    )


def test_task_decompose_description_has_no_one_shot_app_forcing() -> None:
    """Spec: ./spec.md:29-42, ./spec.md:261.

    Source: task_analyzer.md:6-17, node.md:25-27.
    The tool description must not instruct the LLM to prefer a vertical slice
    for one-shot app builds.
    """
    decompose = TaskDecomposeTool()
    description = decompose.description.lower()
    forbidden = ["one-shot app", "vertical-slice", "backend/frontend", "one runnable"]
    for pattern in forbidden:
        assert pattern not in description, (
            f"task_decompose description contains forbidden prompt-category "
            f"guidance: {pattern!r}"
        )


def test_task_decompose_description_requires_material_refinement_benefit() -> None:
    """The tool presents decomposition as adaptive refinement, not an endpoint."""
    description = TaskDecomposeTool().description.lower()

    assert "execution context" in description
    assert "observable evidence for review" in description
    assert "materially improves execution or review" in description
    assert "children recurse under parent" in description
    assert "keep adequate work together" in description
