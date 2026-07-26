"""Model-facing prompts stay task-driven rather than experiment-specific."""

from tinycua.loops.information_digester import (
    _DIGESTER_CONTINUATION,
    _DIGESTER_INSTRUCTION,
)
from tinycua.loops.response_node import _RESPONSE_CONTINUATION
from tinycua.loops.task_nodes import (
    _TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION,
    _TASK_ASSESSOR_UPFRONT_INSTRUCTION,
    _TASK_ANALYZER_CONTINUATION,
    _TASK_ANALYZER_INSTRUCTION,
    _TASK_EXECUTOR_INSTRUCTION,
    _render_active_task_work_order,
)
from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
from tinycua.models.session import Session


def test_prompts_avoid_experiment_specific_artifacts_and_search_counts() -> None:
    rendered = "\n".join(
        (
            _TASK_ANALYZER_CONTINUATION,
            _DIGESTER_INSTRUCTION,
            _DIGESTER_CONTINUATION,
            _RESPONSE_CONTINUATION,
        )
    ).lower()

    for phrase in (
        "write report",
        "report file",
        "markdown with math",
        "model landscape",
        "2-4 searches",
    ):
        assert phrase not in rendered
    assert "requested timeframe" in rendered
    assert "relevant artifacts" in rendered


def test_executor_file_guidance_is_operation_agnostic() -> None:
    session = Session()
    session.task_store.create_task("Produce the requested artifact")

    work_order = _render_active_task_work_order(session).lower()

    assert "least destructive operation" in work_order
    assert "append_file" not in work_order
    assert "first task writing" not in work_order


def test_planning_guidance_is_generic_and_does_not_remove_tools() -> None:
    rendered = "\n".join(
        (
            _TASK_ANALYZER_INSTRUCTION,
            _TASK_ASSESSOR_UPFRONT_INSTRUCTION,
            _TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION,
        )
    ).lower()

    assert "use available tools" in rendered
    assert "exactly three tasks" not in rendered
    assert "mandatory folder" not in rendered
    assert "artifact map" not in rendered


def test_execution_and_review_guidance_preserves_incidental_outcome_evidence() -> None:
    assert "incidentally satisfy pending outcomes" in _TASK_EXECUTOR_INSTRUCTION
    assert "do not claim pending tasks are complete" in _TASK_EXECUTOR_INSTRUCTION
    assert "context_updates" in _RESULT_REVIEWER_INSTRUCTION
    assert "do not approve unfinished tasks" in _RESULT_REVIEWER_INSTRUCTION
