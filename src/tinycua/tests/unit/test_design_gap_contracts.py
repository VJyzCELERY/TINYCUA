"""Contracts for remaining docs/design parity gaps."""

from __future__ import annotations

from pathlib import Path

from tinycua.config.node_config import NodeConfigBase, create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_nodes import TinyCUAResultAggregationNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.session import Session
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.task import (
    AggregatedResult,
    ReviewerDecision,
    TaskResult,
    TaskStateStore,
    TaskStatus,
)
from tinycua.tools.enhanced_context_retrieval import EnhancedContextRetrievalTool


def test_enhanced_context_retrieval_creates_workspace_cache_file(tmp_path: Path) -> None:
    """Context retrieval owns a scoped cache file under the bound workspace."""
    tool = EnhancedContextRetrievalTool()
    tool.bind_workspace(tmp_path)

    result = tool(
        session_context=[
            {"role": "user", "content": "alpha migration plan"},
            {"role": "assistant", "content": "beta execution notes"},
        ],
        query="migration",
        page_size=1,
    )

    cache_path = Path(result["cache_path"])
    assert cache_path.exists()
    assert cache_path.is_relative_to(tmp_path)
    assert result["results"][0]["matched_terms"] == ["migration"]
    assert result["page"]["total_results"] >= 1


def test_response_node_can_suspend_for_information_digestion() -> None:
    """ResponseNode can request a digester and resume from the same queue."""
    response = ResponseNode(config=NodeConfigBase(metadata={"require_digest": True}))
    session = Session()
    response.session = session
    queue = NodeQueue(items=[response])

    response.on_complete(queue, LLMResult(content="need more context"))

    assert [node.node_id for node in queue.items] == ["digester", "response"]
    assert queue.items[0].parent is response
    assert response.config.metadata["digest_requested"] is True


def test_response_node_does_not_resuspend_after_digest_available() -> None:
    """A resumed ResponseNode with digested context terminates normally."""
    response = ResponseNode(config=NodeConfigBase(metadata={"require_digest": True}))
    session = Session()
    from tinycua.models.session_context_entry import SessionContextEntry

    session.session_context.append(
        SessionContextEntry(content=DigestedInformation.fallback("hello"), segment="output")
    )
    response.session = session
    queue = NodeQueue(items=[response])

    response.on_complete(queue, LLMResult(content="final"))

    assert [node.node_id for node in queue.items] == ["response"]


def test_retry_exhaustion_records_chat_audit_not_reusable_context() -> None:
    """Retry exhaustion remains audit/diagnostic data, not downstream LLM context."""
    from tinycua.loops.node import ProcessNode

    node = ProcessNode(node_id="retrying", config=NodeConfigBase(), instruction="work")
    node.session = Session()

    node._record_failure(ValidationResult(is_valid=False, errors=["bad"]), 3)

    assert node.session.session_context == []
    assert node.session.diagnostics[-1]["type"] == "retry_exhausted"
    assert node.session.chat_history[-1].record_type == "retry"
    assert node.session.chat_history[-1].visibility == "internal"


def test_loop_exposes_active_task_helpers() -> None:
    """TinyCUALoop owns public active-task helper APIs from docs/design."""
    session = Session()
    root = session.task_store.create_task("root")
    child = session.task_store.create_task("child", parent_id=root.task_id)
    loop = TinyCUALoop(root_session=session, session_config=SessionConfig())

    assert loop.get_active_task().task_id == child.task_id
    loop.set_active_task(root.task_id)
    assert loop.get_active_task().task_id == root.task_id
    loop.update_active_task_result("root done")
    assert session.task_store.tasks[root.task_id].result.summary == "root done"


def test_result_aggregation_publishes_aggregated_result_context() -> None:
    """Aggregation emits an AggregatedResult for ResponseNode consumption."""
    session = Session()
    root = session.task_store.create_task("root")
    child = session.task_store.create_task("child", parent_id=root.task_id)
    session.task_store.record_result(child.task_id, TaskResult(content="child output"))
    session.task_store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
    # Parent tasks now get a verification pass (executor verifies, reviewer
    # approves). Complete the root so all_done() is true and aggregation fires.
    session.task_store.record_result(root.task_id, TaskResult(content="root verified"))
    session.task_store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
    node = TinyCUAResultAggregationNode(
        node_id="result_aggregation",
        config=create_node_config("result_aggregation"),
    )
    node.session = session

    node.parse_loop_result(LLMResult(content="final context"), None)

    aggregated = [entry.content for entry in session.session_context if isinstance(entry.content, AggregatedResult)]
    assert aggregated
    assert aggregated[-1].root_task_id == root.task_id
    assert "child output" in aggregated[-1].final_context


def test_reviewer_revisions_do_not_escalate_to_response_before_completion() -> None:
    """Reviewer revisions must not synthesize a terminal response mid-task."""
    store = TaskStateStore()
    root = store.create_task("root")
    active = store.create_task("active", parent_id=root.task_id)
    store.transition(active.task_id, TaskStatus.IN_PROGRESS)
    # Use 3 rejections — below the default replan_threshold of 5, so this
    # still routes to executor+reviewer (retry), not replan.
    for _ in range(3):
        store.record_reviewer_decision(active.task_id, ReviewerDecision.NEEDS_REVISION)
    queue = NodeQueue()

    WorkerRuntimeController(store).schedule_after_review(queue)

    assert [node.node_id for node in queue.items] == ["task_executor", "result_reviewer"]
    assert "mandatory_passthrough" not in store.tasks[active.task_id].metadata
