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


def test_task_assessment_decision_schema_uses_task_bound_records() -> None:
    tool = TaskAssessmentDecisionTool()

    assert tool.parameters["required"] == [
        "decision",
        "findings",
        "advisories",
        "rationale",
    ]
    for field, text_field in (("findings", "finding"), ("advisories", "advisory")):
        item = tool.parameters["properties"][field]["items"]
        assert item["required"] == ["task_id", text_field]


@pytest.mark.parametrize(
    ("decision", "findings", "rationale", "error"),
    [
        (
            "ready",
            [{"task_id": "1", "finding": "Too broad"}],
            "Assessment",
            "no blocking",
        ),
        ("analyze", [], "Assessment", "blocking finding"),
        ("later", [], "Assessment", "ready or analyze"),
        ("ready", [], "", "rationale"),
    ],
)
def test_task_assessment_decision_rejects_invalid_shape(
    decision: str,
    findings: list[dict[str, str]],
    rationale: str,
    error: str,
) -> None:
    tool, _store, handoffs = _bound_tool()

    result = tool(
        decision=decision,
        findings=findings,
        advisories=[],
        rationale=rationale,
    )

    assert result["success"] is False
    assert error in result["error"].lower()
    assert handoffs == []


def test_analyze_derives_targets_and_keeps_context_task_local() -> None:
    tool, store, handoffs = _bound_tool()
    number_map = store.task_number_map()
    target_id, sibling_id = number_map[1], number_map[2]

    result = tool(
        decision="analyze",
        findings=[{"task_id": "1", "finding": "Contains two distinct concerns."}],
        advisories=[{"task_id": "1", "advisory": "Keep the shared constraint."}],
        rationale="Refine the first task.",
    )

    assert result["selected_task_ids"] == [target_id]
    assert handoffs[0].payload["selected_task_ids"] == [target_id]
    assert handoffs[0].payload["findings"][0]["task_id"] == target_id
    assert (
        store.tasks[target_id]
        .metadata["planning_finding"]["finding"]
        .startswith("Contains")
    )
    assert (
        store.tasks[target_id]
        .metadata["planning_advisories"][0]["advisory"]
        .startswith("Keep")
    )
    assert "planning_finding" not in store.tasks[sibling_id].metadata
    assert "planning_advisories" not in store.tasks[sibling_id].metadata


def test_analyze_rejects_multiple_findings_for_one_task() -> None:
    tool, store, handoffs = _bound_tool()
    target_id = store.task_number_map()[1]

    result = tool(
        decision="analyze",
        findings=[
            {"task_id": target_id, "finding": "First defect."},
            {"task_id": target_id, "finding": "Second defect."},
        ],
        advisories=[],
        rationale="Refine it.",
    )

    assert result["success"] is False
    assert "one blocking finding per task" in result["error"].lower()
    assert handoffs == []


def test_fresh_finding_clears_stale_planning_resolution() -> None:
    tool, store, _handoffs = _bound_tool()
    target_id = store.task_number_map()[1]
    store.tasks[target_id].metadata.update(
        {
            "planning_note": "Old note.",
            "planning_resolution": {"summary": "Old resolution."},
        }
    )

    result = tool(
        decision="analyze",
        findings=[{"task_id": target_id, "finding": "Fresh defect."}],
        advisories=[],
        rationale="Refine it.",
    )

    assert result["success"] is True
    assert store.tasks[target_id].metadata["planning_note"] == ""
    assert "planning_resolution" not in store.tasks[target_id].metadata


def test_ready_may_store_targeted_advisories() -> None:
    tool, store, handoffs = _bound_tool()
    target_id = store.task_number_map()[1]

    result = tool(
        decision="ready",
        findings=[],
        advisories=[{"task_id": target_id, "advisory": "Verify the existing seam."}],
        rationale="The roadmap can execute.",
    )

    assert result["success"] is True
    assert result["selected_task_ids"] == []
    assert (
        store.tasks[target_id].metadata["planning_advisories"][0]["advisory"]
        == "Verify the existing seam."
    )
    assert handoffs[0].payload["decision"] == "ready"


@pytest.mark.parametrize("status", [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
def test_finding_rejects_finished_or_unknown_target(status: TaskStatus) -> None:
    tool, store, handoffs = _bound_tool()
    task_id = store.task_number_map()[1]
    store.tasks[task_id].status = status

    result = tool(
        decision="analyze",
        findings=[{"task_id": task_id, "finding": "Needs analysis."}],
        advisories=[],
        rationale="Needs analysis.",
    )

    assert result["success"] is False
    assert "valid unfinished task" in result["error"]
    assert handoffs == []


def test_final_assessment_preserves_findings_as_exhausted_advisories() -> None:
    tool, store, handoffs = _bound_tool()
    target_id = store.task_number_map()[1]
    tool.bind_assessment_mode("final_assessment")

    result = tool(
        decision="analyze",
        findings=[{"task_id": target_id, "finding": "Could still be narrower."}],
        advisories=[],
        rationale="Budget ended.",
    )

    assert result["decision"] == "analyze"
    assert result["selected_task_ids"] == [target_id]
    assert result["analysis_budget_exhausted"] is True
    advisory = store.tasks[target_id].metadata["planning_advisories"][0]
    assert advisory["advisory"] == "Could still be narrower."
    assert advisory["analysis_budget_exhausted"] is True
    assert handoffs[0].payload["analysis_budget_exhausted"] is True
