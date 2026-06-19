"""Mission population and constraint propagation contracts (FR-001, FR-002).

Covers:
- The loop populates root.metadata["mission"] + inherited_constraints after
  TaskCreate completes, from DigestedInformation in root session_context
  (or raw user query fallback).
- TaskDecomposeTool propagates inherited_constraints from parent to children.
"""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry
from tinycua.tools.task_tools import TaskDecomposeTool, TaskInitTool


def _task_create_node(session: Session) -> TinyCUATaskCreateNode:
    """Build a TaskCreateNode bound to a session."""
    node = TinyCUATaskCreateNode(
        node_id="task_create",
        config=create_node_config("task_create"),
    )
    node.ensure_session(session)
    return node


def test_mission_populated_from_digested_information() -> None:
    """Root task mission is derived from DigestedInformation when present."""
    loop = TinyCUALoop()
    loop.root_session.session_context.append(
        SessionContextEntry(
            segment="output",
            content=DigestedInformation(
                context_summary="Build a clock app.",
                original_query="Make an analog clock animation in a single HTML file.",
                constraints=["Deliver exactly one self-contained HTML file."],
            ),
        )
    )
    # Simulate task_init having created the root task.
    init = TaskInitTool()
    init.bind_task_store(loop.root_session.task_store)
    init(title="Build clock app")
    node = _task_create_node(loop.root_session)

    loop._maybe_populate_root_mission(node)

    root = loop.root_session.task_store.tasks[loop.root_session.task_store.root_task_id]
    assert root.metadata["mission"] == (
        "Make an analog clock animation in a single HTML file."
    )
    assert root.metadata["inherited_constraints"] == [
        "Deliver exactly one self-contained HTML file.",
    ]


def test_mission_falls_back_to_raw_user_query() -> None:
    """Without a digest, mission is derived from the raw user query."""
    loop = TinyCUALoop()
    loop.root_session.input_context = [
        {"role": "user", "content": "Write a markdown report on transformers."},
    ]
    init = TaskInitTool()
    init.bind_task_store(loop.root_session.task_store)
    init(title="Write report")
    node = _task_create_node(loop.root_session)

    loop._maybe_populate_root_mission(node)

    root = loop.root_session.task_store.tasks[loop.root_session.task_store.root_task_id]
    assert root.metadata["mission"] == "Write a markdown report on transformers."
    assert root.metadata["inherited_constraints"] == []


def test_mission_not_overwritten_on_repeat_call() -> None:
    """Re-running population does not clobber an existing mission."""
    loop = TinyCUALoop()
    loop.root_session.session_context.append(
        SessionContextEntry(
            segment="output",
            content=DigestedInformation(
                original_query="First mission.",
                constraints=["first constraint"],
            ),
        )
    )
    init = TaskInitTool()
    init.bind_task_store(loop.root_session.task_store)
    init(title="Root")
    node = _task_create_node(loop.root_session)
    loop._maybe_populate_root_mission(node)

    # A second digest appears (later in context) with a different query.
    loop.root_session.session_context.append(
        SessionContextEntry(
            segment="output",
            content=DigestedInformation(
                original_query="Different later mission.",
                constraints=["later constraint"],
            ),
        )
    )
    loop._maybe_populate_root_mission(node)

    root = loop.root_session.task_store.tasks[loop.root_session.task_store.root_task_id]
    assert root.metadata["mission"] == "First mission."
    assert root.metadata["inherited_constraints"] == ["first constraint"]


def test_mission_not_populated_for_non_task_create_node() -> None:
    """Only task_create triggers mission population; other nodes are no-ops."""
    loop = TinyCUALoop()
    loop.root_session.session_context.append(
        SessionContextEntry(
            segment="output",
            content=DigestedInformation(original_query="Should be ignored."),
        )
    )
    init = TaskInitTool()
    init.bind_task_store(loop.root_session.task_store)
    init(title="Root")
    from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode

    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(loop.root_session)

    loop._maybe_populate_root_mission(node)

    root = loop.root_session.task_store.tasks[loop.root_session.task_store.root_task_id]
    assert "mission" not in root.metadata


def test_task_decompose_propagates_inherited_constraints() -> None:
    """Child tasks inherit inherited_constraints from the parent on decompose."""
    store = Session().task_store
    root = store.create_task("Build clock app")
    root.metadata["inherited_constraints"] = [
        "Deliver exactly one self-contained HTML file."
    ]
    decompose = TaskDecomposeTool()
    decompose.bind_task_store(store)

    result = decompose(task_id=root.task_id, subtasks=["Clock face", "Animation"])

    child_ids = result["child_task_ids"]
    for child_id in child_ids:
        child = store.tasks[child_id]
        assert child.metadata["inherited_constraints"] == [
            "Deliver exactly one self-contained HTML file."
        ]


def test_task_decompose_preserves_existing_child_constraints() -> None:
    """Decompose must not overwrite constraints a child already carries."""
    store = Session().task_store
    parent = store.create_task("Parent")
    parent.metadata["inherited_constraints"] = ["parent constraint"]
    # Pre-existing child (created directly, not via decompose).
    existing = store.create_task("Existing", parent_id=parent.task_id)
    existing.metadata["inherited_constraints"] = ["own constraint"]
    decompose = TaskDecomposeTool()
    decompose.bind_task_store(store)

    # Decompose is idempotent — parent already has children, returns them as-is.
    result = decompose(task_id=parent.task_id, subtasks=["Should be ignored"])

    assert result["success"] is True
    assert store.tasks[result["child_task_ids"][0]].metadata[
        "inherited_constraints"
    ] == ["own constraint"]


if __name__ == "__main__":
    # ponytail: self-check
    test_mission_populated_from_digested_information()
    test_mission_falls_back_to_raw_user_query()
    test_mission_not_overwritten_on_repeat_call()
    test_mission_not_populated_for_non_task_create_node()
    test_task_decompose_propagates_inherited_constraints()
    test_task_decompose_preserves_existing_child_constraints()
    print("ok")
