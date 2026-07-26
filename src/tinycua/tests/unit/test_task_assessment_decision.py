"""TaskAssessor decision boundary tests."""

from __future__ import annotations

import pytest

from tinycua.models.task import TaskStateStore, TaskStatus
from tinycua.tools.handoff_tools import TaskAssessmentDecisionTool


def _bound_tool() -> tuple[TaskAssessmentDecisionTool, TaskStateStore, list]:
    store = TaskStateStore()
    root = store.create_task("Root")
    store.create_task("First", parent_id=root.task_id)
    store.create_task("Second", parent_id=root.task_id)
    handoffs = []
    tool = TaskAssessmentDecisionTool()
    tool.bind_task_store(store)
    tool.bind_handoff_store(handoffs)
    tool.bind_source_node("task_assessor")
    return tool, store, handoffs


def test_task_assessment_decision_schema_requires_all_fields() -> None:
    tool = TaskAssessmentDecisionTool()

    assert tool.name == "task_assessment_decision"
    assert tool.parameters["required"] == [
        "decision",
        "selected_task_ids",
        "rationale",
    ]
    assert tool.parameters["properties"]["decision"]["enum"] == [
        "ready",
        "analyze",
    ]


@pytest.mark.parametrize(
    ("decision", "selected_task_ids", "error"),
    [
        ("ready", ["1"], "empty"),
        ("analyze", [], "nonempty"),
        ("later", [], "ready or analyze"),
        ("ready", [], "rationale"),
    ],
)
def test_task_assessment_decision_rejects_invalid_shape(
    decision: str,
    selected_task_ids: list[str],
    error: str,
) -> None:
    tool, _store, handoffs = _bound_tool()

    result = tool(
        decision=decision,
        selected_task_ids=selected_task_ids,
        rationale="" if error == "rationale" else "Assessment",
    )

    assert result["success"] is False
    assert error in result["error"].lower()
    assert handoffs == []


def test_task_assessment_decision_canonicalizes_unfinished_task_ids() -> None:
    tool, store, handoffs = _bound_tool()
    expected_id = store.task_number_map()[1]

    result = tool(
        decision="analyze",
        selected_task_ids=["1"],
        rationale="The first task needs decomposition.",
    )

    assert result["success"] is True
    assert result["selected_task_ids"] == [expected_id]
    assert len(handoffs) == 1
    assert handoffs[0].target_node == "task_analyzer"
    assert handoffs[0].payload == {
        "decision": "analyze",
        "selected_task_ids": [expected_id],
        "rationale": "The first task needs decomposition.",
    }


@pytest.mark.parametrize("status", [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
def test_task_assessment_decision_rejects_finished_or_unknown_tasks(
    status: TaskStatus,
) -> None:
    tool, store, handoffs = _bound_tool()
    task_id = store.task_number_map()[1]
    store.tasks[task_id].status = status

    result = tool(
        decision="analyze",
        selected_task_ids=[task_id, "missing"],
        rationale="Needs analysis.",
    )

    assert result["success"] is False
    assert "unfinished" in result["error"].lower()
    assert handoffs == []


def test_task_assessment_ready_emits_empty_analyzer_handoff() -> None:
    tool, _store, handoffs = _bound_tool()

    result = tool(
        decision="ready",
        selected_task_ids=[],
        rationale="The roadmap is executable.",
    )

    assert result["success"] is True
    assert handoffs[0].target_node == "task_analyzer"
    assert handoffs[0].payload["decision"] == "ready"
    assert handoffs[0].payload["selected_task_ids"] == []


def test_task_assessment_decision_rejects_unknown_task() -> None:
    tool, _store, handoffs = _bound_tool()

    result = tool(
        decision="analyze",
        selected_task_ids=["missing"],
        rationale="Needs analysis.",
    )

    assert result["success"] is False
    assert "valid unfinished task" in result["error"]
    assert handoffs == []


def test_task_assessment_decision_rejects_blank_task_reference() -> None:
    tool, _store, handoffs = _bound_tool()

    result = tool(
        decision="analyze",
        selected_task_ids=["  "],
        rationale="Needs analysis.",
    )

    assert result["success"] is False
    assert "valid unfinished task" in result["error"]
    assert handoffs == []
