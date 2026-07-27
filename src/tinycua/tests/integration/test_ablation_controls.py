"""Contracts for Information Digester and Result Reviewer ablations."""

from __future__ import annotations

from tinycua.config.node_config import NodeConfigBase, create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.node_input import NodeInput
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session
from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus


def _decision(route: str) -> DecisionResult:
    """Build a Worker route decision."""
    result = LLMResult(content="")
    return DecisionResult(route, result, result)


def _no_digest_worker(session: Session) -> TinyCUAWorkerNode:
    """Build a Worker configured to receive a direct CEQ handoff."""
    config = create_node_config("worker")
    config.metadata["session_config"] = SessionConfig(digest_enabled=False)
    worker = TinyCUAWorkerNode("worker", config)
    worker.ensure_session(session)
    worker._current_ceq = NodeInput(  # noqa: SLF001 - route handoff contract.
        input_type="context_enhanced_query",
        source_node="query_analyst",
        target_node="worker",
        messages=[{"role": "assistant", "content": "Context Enhanced Query:\nLatest"}],
        metadata={"original_query": "Latest"},
    )
    return worker


def test_ablation_controls_default_enabled_and_cli_flags_are_independent() -> None:
    """Controls preserve full behavior by default and independently disable nodes."""
    from tinycua.cli.run import parse_args

    assert SessionConfig().digest_enabled is True
    assert SessionConfig().review_enabled is True
    args = parse_args(["--no-digest", "task"])
    assert args.no_digest is True
    assert args.no_review is False
    args = parse_args(["--no-review", "task"])
    assert args.no_digest is False
    assert args.no_review is True


def test_no_digest_query_analyst_hands_unchanged_ceq_to_worker() -> None:
    """Disabled digestion queues Worker directly without reusing an old digest."""
    config = create_node_config("query_analyst")
    config.metadata["session_config"] = SessionConfig(digest_enabled=False)
    query = TinyCUAQueryAnalystNode("query_analyst", config)
    session = Session(input_context=[{"role": "user", "content": "Latest"}])
    session.session_context.append(
        {"role": "assistant", "content": DigestedInformation(original_query="Old")}
    )
    query.ensure_session(session)
    query._current_context_summary = "Latest request context."  # noqa: SLF001
    queue = NodeQueue(items=[query, ResponseNode()])
    query._queue = queue  # noqa: SLF001 - routing integration setup.

    query._route_worker()

    assert [node.node_id for node in queue.items] == [
        "query_analyst",
        "worker",
        "response",
    ]
    handoff = queue._inputs["worker"]  # noqa: SLF001 - queue contract.
    assert handoff.input_type == "context_enhanced_query"
    assert handoff.target_node == "worker"
    assert handoff.metadata["original_query"] == "Latest"


def test_no_digest_worker_preserves_archive_and_overlay_for_every_route() -> None:
    """Direct CEQ routes retain existing tree and overlay semantics."""
    session = Session()
    root = session.task_store.create_task("Root")
    root.metadata["current_context_overlay"] = {"context_summary": "Earlier"}
    worker = _no_digest_worker(session)
    queue = NodeQueue(items=[worker])

    worker.on_complete(queue, _decision("task_reanalysis"))

    assert [node.node_id for node in queue.items] == [
        "worker",
        "task_analyzer",
        "analysis_effort",
        "task_executor",
        "result_reviewer",
    ]
    assert root.metadata["current_context_overlay"] == {"context_summary": "Earlier"}
    assert queue._inputs["task_analyzer"].input_type == "context_enhanced_query"  # noqa: SLF001

    session = Session()
    old_root = session.task_store.create_task("Old")
    worker = _no_digest_worker(session)
    queue = NodeQueue(items=[worker])
    worker.on_complete(queue, _decision("task_recreation"))
    TinyCUALoop(root_session=session)._publish_structured_outputs_to_root(worker)

    assert session.task_store.root_task_id is None
    assert queue._inputs["task_create"].input_type == "context_enhanced_query"  # noqa: SLF001
    assert any(
        entry.content.get("archive_type") == "task_tree"
        for entry in session.session_context
        if isinstance(entry.content, dict)
    )
    assert old_root.task_id

    session = Session()
    root = session.task_store.create_task("Root")
    root.metadata["current_context_overlay"] = {"context_summary": "Earlier"}
    worker = _no_digest_worker(session)
    queue = NodeQueue(items=[worker])
    worker.on_complete(queue, _decision("proceed_execution"))
    assert [node.node_id for node in queue.items] == [
        "worker",
        "task_executor",
        "result_reviewer",
    ]
    assert queue._inputs["task_executor"].input_type == "context_enhanced_query"  # noqa: SLF001
    assert root.metadata["current_context_overlay"] == {"context_summary": "Earlier"}


def test_no_review_worker_omits_reviewer_from_initial_queue() -> None:
    """Reviewer disablement changes only reviewer queue entries."""
    config = create_node_config("worker")
    config.metadata["session_config"] = SessionConfig(review_enabled=False)
    worker = TinyCUAWorkerNode("worker", config)
    worker.ensure_session(Session())
    queue = NodeQueue(items=[worker])

    worker.on_complete(queue, _decision("task_creation"))

    assert [node.node_id for node in queue.items] == [
        "worker",
        "task_create",
        "task_analyzer",
        "analysis_effort",
        "task_executor",
    ]


def test_no_digest_response_node_does_not_suspend() -> None:
    """A disabled digester bypasses optional final-response suspension."""
    response = ResponseNode(
        config=NodeConfigBase(
            metadata={
                "require_digest": True,
                "session_config": SessionConfig(digest_enabled=False),
            }
        )
    )
    response.ensure_session(Session())
    queue = NodeQueue(items=[response])

    response.on_complete(queue, LLMResult(content="answer"))

    assert [node.node_id for node in queue.items] == ["response"]


def test_no_review_runtime_completes_retries_then_replans_without_reviewer_nodes() -> (
    None
):
    """Validated executor reports schedule deterministic no-review outcomes."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.record_result(active.task_id, TaskResult(content="failed", success=False))
    controller = WorkerRuntimeController(
        store, review_enabled=False, replan_threshold=2
    )
    queue = NodeQueue()

    controller.schedule_after_execution(queue, active.task_id)

    assert [node.node_id for node in queue.items] == ["task_executor"]
    assert active.metadata["no_review_failures"] == 1
    store.record_result(
        active.task_id, TaskResult(content="failed again", success=False)
    )
    queue = NodeQueue()
    controller.schedule_after_execution(queue, active.task_id)
    assert [node.node_id for node in queue.items] == ["task_analyzer", "task_executor"]
    assert active.reviewer_decisions == []

    store.record_result(active.task_id, TaskResult(content="done", success=True))
    queue = NodeQueue()
    controller.schedule_after_execution(queue, active.task_id)
    assert active.status == TaskStatus.COMPLETED
    assert [node.node_id for node in queue.items] == ["task_executor"]


def test_state_snapshot_records_ablation_configuration() -> None:
    """Runtime exports retain the effective experimental condition."""
    loop = TinyCUALoop(
        session_config=SessionConfig(digest_enabled=False, review_enabled=True)
    )

    metadata = loop.get_state_snapshot()["run_metadata"]
    assert metadata["digest_enabled"] is False
    assert metadata["review_enabled"] is True
    assert metadata["source_revision"]
    assert metadata["configuration"] == {
        "worker_effort": "medium",
        "replan_threshold": 5,
    }
