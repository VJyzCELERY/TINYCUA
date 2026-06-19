"""Mission block rendering in worker-internal node continuations (FR-003)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import (
    TinyCUAResultAggregationNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.session import Session
from tinycua.models.task import TaskResult


def _session_with_mission(
    mission: str = "", constraints: list[str] | None = None
) -> Session:
    """Build a session whose root task carries a mission + constraints."""
    session = Session()
    root = session.task_store.create_task("Root goal")
    root.metadata["mission"] = mission
    root.metadata["inherited_constraints"] = constraints or []
    child = session.task_store.create_task("Child task", parent_id=root.task_id)
    child.metadata["inherited_constraints"] = constraints or []
    session.task_store.record_result(
        child.task_id, TaskResult(content="done", success=True)
    )
    return session


def test_task_analyzer_renders_mission_block() -> None:
    session = _session_with_mission(
        "Build a clock app in a single HTML file.", ["single file"]
    )
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Mission" in prompt
    assert "Build a clock app in a single HTML file." in prompt
    assert "single file" in prompt


def test_task_assessor_renders_mission_block() -> None:
    session = _session_with_mission("Research transformers.", ["use markdown"])
    node = TinyCUATaskAssessorNode(
        node_id="task_assessor", config=create_node_config("task_assessor")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Mission" in prompt
    assert "Research transformers." in prompt
    assert "use markdown" in prompt


def test_task_executor_renders_mission_block() -> None:
    session = _session_with_mission("Make an analog clock.", ["single HTML file"])
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Mission" in prompt
    assert "Make an analog clock." in prompt
    assert "single HTML file" in prompt


def test_result_reviewer_renders_mission_block() -> None:
    session = _session_with_mission("Build a Notion clone.", ["python backend"])
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Mission" in prompt
    assert "Build a Notion clone." in prompt
    assert "python backend" in prompt


def test_result_aggregation_renders_mission_block() -> None:
    session = _session_with_mission("Write a report.", ["markdown"])
    node = TinyCUAResultAggregationNode(
        node_id="result_aggregation", config=create_node_config("result_aggregation")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Mission" in prompt
    assert "Write a report." in prompt


def test_mission_block_empty_when_no_mission() -> None:
    """When no mission is set, no ## Mission block is rendered (no-op)."""
    session = Session()
    session.task_store.create_task("Root")
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Mission" not in prompt


if __name__ == "__main__":
    # ponytail: self-check
    test_task_analyzer_renders_mission_block()
    test_task_assessor_renders_mission_block()
    test_task_executor_renders_mission_block()
    test_result_reviewer_renders_mission_block()
    test_result_aggregation_renders_mission_block()
    test_mission_block_empty_when_no_mission()
    print("ok")
