"""Unit tests for reviewer rationale validation evidence enforcement (FR-059)."""

from __future__ import annotations

import json

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode, TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStatus


def _reviewer_node(session) -> TinyCUAResultReviewerNode:
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer",
        config=create_node_config("result_reviewer"),
    )
    node.ensure_session(session)
    return node


def _executor_node(session) -> TinyCUATaskExecutorNode:
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    node.ensure_session(session)
    return node


def _review_decision_call(
    decision: str,
    rationale: str = "",
    task_id: str | None = None,
) -> list[dict]:
    """Build a tool_calls list with one task_review_decision call."""
    arguments = {"decision": decision, "rationale": rationale}
    if task_id:
        arguments["task_id"] = task_id
    return [
        {
            "function": {
                "name": "task_review_decision",
                "arguments": json.dumps(arguments),
            }
        }
    ]


def _review_decision_result(
    decision: str,
    task_id: str,
    status: str = "completed",
) -> list[dict]:
    """Build a tool_results list with one task_review_decision result."""
    return [
        {
            "name": "task_review_decision",
            "output": {
                "success": True,
                "task_id": task_id,
                "decision": decision,
                "status": status,
            },
        }
    ]


def _setup_task_with_result():
    """Create a loop with a task that has a result ready for review."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    child = store.create_task("Child", parent_id=root.task_id)
    store.transition(child.task_id, TaskStatus.IN_PROGRESS)
    store.record_result(child.task_id, TaskResult(content="done", success=True))
    return loop, child.task_id


class TestApprovedRequiresValidatedTag:
    """Approved decisions must include [validated]: in the rationale."""

    def test_approved_without_validated_fails(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="approved",
            tool_calls=_review_decision_call(
                "approved",
                rationale="looks good to me",
                task_id=task_id,
            ),
            metadata={"tool_results": _review_decision_result("approved", task_id)},
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)

        assert not validation.is_valid
        assert any("[validated]" in e for e in validation.errors)

    def test_approved_with_validated_passes(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="approved",
            tool_calls=_review_decision_call(
                "approved",
                rationale="[validated]: pytest tests/ -q exit_code=0 confirms all pass",
                task_id=task_id,
            ),
            metadata={"tool_results": _review_decision_result("approved", task_id)},
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert validation.is_valid

    def test_approved_with_validated_case_insensitive(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="approved",
            tool_calls=_review_decision_call(
                "approved",
                rationale="[VALIDATED]: grep -c pass report.md → 5",
                task_id=task_id,
            ),
            metadata={"tool_results": _review_decision_result("approved", task_id)},
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert validation.is_valid


class TestNonApprovedRequiresValidateTag:
    """Non-approved decisions must include [validate]: in the rationale."""

    def test_needs_revision_without_validate_fails(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="needs revision",
            tool_calls=_review_decision_call(
                "needs_revision",
                rationale="the report is missing a conclusion section",
                task_id=task_id,
            ),
            metadata={
                "tool_results": _review_decision_result(
                    "needs_revision", task_id, status="in_progress"
                )
            },
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert not validation.is_valid
        assert any("[validate]" in e for e in validation.errors)

    def test_needs_revision_with_validate_passes(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="needs revision",
            tool_calls=_review_decision_call(
                "needs_revision",
                rationale=(
                    "[finding]: report has duplicate ## Conclusion headers "
                    "[validate]: grep -c '## Conclusion' report.md"
                ),
                task_id=task_id,
            ),
            metadata={
                "tool_results": _review_decision_result(
                    "needs_revision", task_id, status="in_progress"
                )
            },
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert validation.is_valid

    def test_rejected_with_validate_passes(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="rejected",
            tool_calls=_review_decision_call(
                "rejected",
                rationale=(
                    "[finding]: claimed GPT-6 exists but it doesn't "
                    "[validate]: web_search 'GPT-6 OpenAI 2026'"
                ),
                task_id=task_id,
            ),
            metadata={
                "tool_results": _review_decision_result(
                    "needs_revision", task_id, status="in_progress"
                )
            },
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert validation.is_valid

    def test_replan_with_validate_passes(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="replan",
            tool_calls=_review_decision_call(
                "replan",
                rationale=(
                    "[finding]: the plan doesn't cover testing "
                    "[validate]: grep -c pytest tasks/"
                ),
                task_id=task_id,
            ),
            metadata={
                "tool_results": _review_decision_result(
                    "needs_revision", task_id, status="in_progress"
                )
            },
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert validation.is_valid


class TestEmptyOrMissingRationale:
    """Empty or missing rationale fails validation."""

    def test_empty_rationale_fails(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        llm_result = LLMResult(
            content="approved",
            tool_calls=_review_decision_call("approved", rationale="", task_id=task_id),
            metadata={"tool_results": _review_decision_result("approved", task_id)},
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert not validation.is_valid
        assert any("rationale" in e.lower() for e in validation.errors)

    def test_missing_rationale_key_fails(self):
        loop, task_id = _setup_task_with_result()
        node = _reviewer_node(loop.root_session)
        # No rationale key in arguments at all.
        llm_result = LLMResult(
            content="approved",
            tool_calls=[
                {
                    "function": {
                        "name": "task_review_decision",
                        "arguments": json.dumps({"decision": "approved", "task_id": task_id}),
                    }
                }
            ],
            metadata={"tool_results": _review_decision_result("approved", task_id)},
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert not validation.is_valid


class TestNonReviewerNodeSkips:
    """The validator only applies to result_reviewer nodes."""

    def test_executor_node_skips_validation(self):
        loop, task_id = _setup_task_with_result()
        node = _executor_node(loop.root_session)
        llm_result = LLMResult(
            content="done",
            tool_calls=_review_decision_call("approved", rationale="", task_id=task_id),
            metadata={"tool_results": _review_decision_result("approved", task_id)},
        )

        validation = loop._validate_result_reviewer_rationale_evidence(node, llm_result)
        assert validation.is_valid  # no errors — validator skipped


class TestRationaleIsRequiredParam:
    """The TaskReviewDecisionTool schema marks rationale as required."""

    def test_rationale_in_required_list(self):
        from tinycua.tools.task_tools import TaskReviewDecisionTool

        tool = TaskReviewDecisionTool()
        assert "rationale" in tool.parameters.get("required", [])

    def test_rationale_has_description(self):
        from tinycua.tools.task_tools import TaskReviewDecisionTool

        tool = TaskReviewDecisionTool()
        rationale_prop = tool.parameters.get("properties", {}).get("rationale", {})
        assert isinstance(rationale_prop, dict)
        assert "description" in rationale_prop