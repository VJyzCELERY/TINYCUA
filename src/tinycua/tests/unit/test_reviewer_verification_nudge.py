"""Reviewer verification soft nudge contracts (FR-008, FR-009).

Covers:
- ResultReviewer instruction requires read-only verification evidence for
  file artifacts (or states why skipped).
- A soft transcript note (NEVER a validation crash) is recorded when the
  reviewer approves a task with file artifacts but called no read-only
  verification tool in the batch.
"""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskResult


def _reviewer_node(session) -> TinyCUAResultReviewerNode:
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )
    node.ensure_session(session)
    return node


def _approved_batch(task_id: str, *, with_readonly: bool = False) -> list[dict]:
    """Build a tool_results batch with an approval (+ optional read-only tool)."""
    batch = [
        {
            "name": "task_review_decision",
            "output": {
                "success": True,
                "task_id": task_id,
                "decision": "approved",
                "status": "completed",
            },
        },
        {"name": "task_inspect", "output": {"success": True, "tasks": {}}},
        {"name": "terminate", "output": {"success": True}},
    ]
    if with_readonly:
        batch.insert(
            0,
            {"name": "read_file", "output": {"success": True, "path": "app.py"}},
        )
    return batch


def test_approval_without_readonly_verification_records_soft_nudge() -> None:
    """Approving a file-artifact task with no read-only tool adds a transcript note.

    This is a SOFT nudge — it must NOT set validation.is_valid=False (no crash).
    See FR-009.
    """
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    task = store.create_task("Build app", parent_id=root.task_id)
    task.artifacts.append({"path": "app.py", "kind": "file", "metadata": {}})
    store.record_result(task.task_id, TaskResult(content="done", success=True))
    store.record_reviewer_decision(task.task_id, "approved")
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="approved",
        metadata={"tool_results": _approved_batch(task.task_id)},
    )

    # First confirm the full validation is valid (no crash).
    validation = loop._validate_node_result(node, llm_result)
    assert validation.is_valid

    # Now run the soft nudge and confirm a transcript note was recorded.
    before = len(loop.get_transcript_events())
    loop._maybe_warn_reviewer_no_verification(node, llm_result)
    after = len(loop.get_transcript_events())
    assert after > before


def test_approval_with_readonly_verification_records_no_nudge() -> None:
    """Approving with a read-only tool present produces no nudge."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    task = store.create_task("Build app", parent_id=root.task_id)
    task.artifacts.append({"path": "app.py", "kind": "file", "metadata": {}})
    store.record_result(task.task_id, TaskResult(content="done", success=True))
    store.record_reviewer_decision(task.task_id, "approved")
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="approved",
        metadata={"tool_results": _approved_batch(task.task_id, with_readonly=True)},
    )

    before = len(loop.get_transcript_events())
    loop._maybe_warn_reviewer_no_verification(node, llm_result)
    after = len(loop.get_transcript_events())
    assert before == after  # no new transcript note


def test_nudge_skipped_when_no_artifacts() -> None:
    """A task with no file artifacts does not trigger the nudge."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    task = store.create_task("Research task", parent_id=root.task_id)
    store.record_result(task.task_id, TaskResult(content="researched", success=True))
    store.record_reviewer_decision(task.task_id, "approved")
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="approved",
        metadata={"tool_results": _approved_batch(task.task_id)},
    )

    before = len(loop.get_transcript_events())
    loop._maybe_warn_reviewer_no_verification(node, llm_result)
    after = len(loop.get_transcript_events())
    assert before == after


def test_nudge_skipped_for_non_reviewer_node() -> None:
    """Only the result_reviewer node triggers the nudge."""
    from tinycua.loops.task_nodes import TinyCUATaskExecutorNode

    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    node.ensure_session(loop.root_session)
    llm_result = LLMResult(
        content="done",
        metadata={
            "tool_results": [
                {"name": "task_result_update", "output": {"success": True}}
            ]
        },
    )

    before = len(loop.get_transcript_events())
    loop._maybe_warn_reviewer_no_verification(node, llm_result)
    after = len(loop.get_transcript_events())
    assert before == after


def test_nudge_skipped_when_no_approval_in_batch() -> None:
    """A reviewer batch with no approval (e.g. needs_revision) does not nudge."""
    loop = TinyCUALoop()
    store = loop.root_session.task_store
    root = store.create_task("Root")
    task = store.create_task("Build app", parent_id=root.task_id)
    task.artifacts.append({"path": "app.py", "kind": "file", "metadata": {}})
    store.record_result(task.task_id, TaskResult(content="done", success=True))
    node = _reviewer_node(loop.root_session)
    llm_result = LLMResult(
        content="needs revision",
        metadata={
            "tool_results": [
                {
                    "name": "task_review_decision",
                    "output": {
                        "success": True,
                        "task_id": task.task_id,
                        "decision": "needs_revision",
                    },
                },
                {"name": "task_inspect", "output": {"success": True, "tasks": {}}},
            ]
        },
    )

    before = len(loop.get_transcript_events())
    loop._maybe_warn_reviewer_no_verification(node, llm_result)
    after = len(loop.get_transcript_events())
    assert before == after


if __name__ == "__main__":
    # ponytail: self-check
    test_approval_without_readonly_verification_records_soft_nudge()
    test_approval_with_readonly_verification_records_no_nudge()
    test_nudge_skipped_when_no_artifacts()
    test_nudge_skipped_for_non_reviewer_node()
    test_nudge_skipped_when_no_approval_in_batch()
    print("ok")
