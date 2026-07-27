"""Worker re-digestion, overlay, and root-recreation contracts."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session
from tinycua.models.session_context_entry import entry_content


def _decision(route: str) -> DecisionResult:
    """Build a minimal Worker route decision."""
    result = LLMResult(content="")
    return DecisionResult(route, result, result)


def _worker(session: Session, digest: DigestedInformation) -> TinyCUAWorkerNode:
    """Build a Worker with its current digested input already committed."""
    worker = TinyCUAWorkerNode("worker", create_node_config("worker"))
    worker.ensure_session(session)
    worker._current_digest = digest  # noqa: SLF001 - committed digester handoff.
    return worker


def test_query_analyst_redigests_when_session_already_has_a_digest() -> None:
    """Every Worker entry consolidates the new query with prior session context."""
    session = Session(input_context=[{"role": "user", "content": "Latest request"}])
    session.session_context.append(
        {"role": "assistant", "content": DigestedInformation(original_query="Old")}
    )
    query = TinyCUAQueryAnalystNode(
        "query_analyst", create_node_config("query_analyst")
    )
    query.ensure_session(session)
    queue = NodeQueue(items=[query])
    query._queue = queue  # noqa: SLF001 - routing integration setup.

    query._route_worker()

    assert [node.node_id for node in queue.items] == [
        "query_analyst",
        "digester",
        "worker",
    ]


def test_task_recreation_archives_old_tree_and_restarts_at_task_create() -> None:
    """Recreation retains old work as retrieval context but starts a fresh root."""
    session = Session()
    old_root = session.task_store.create_task("Old root")
    session.task_store.create_task("Unfinished old work", parent_id=old_root.task_id)
    digest = DigestedInformation(
        context_summary="New objective summary.",
        original_query="Start a new objective.",
    )
    worker = _worker(session, digest)
    queue = NodeQueue(items=[worker])

    worker.on_complete(queue, _decision("task_recreation"))
    TinyCUALoop(root_session=session)._publish_structured_outputs_to_root(worker)

    assert session.task_store.root_task_id is None
    assert [node.node_id for node in queue.items] == [
        "worker",
        "task_create",
        "task_analyzer",
        "analysis_effort",
        "task_executor",
        "result_reviewer",
    ]
    archive = next(
        entry_content(entry)
        for entry in session.session_context
        if isinstance(entry_content(entry), dict)
        and entry_content(entry).get("archive_type") == "task_tree"
    )
    assert archive["reason"] == "task_recreation"
    assert archive["task_tree"]["root_task_id"] == old_root.task_id
    handoff = queue._inputs[queue.items[1].node_id]  # noqa: SLF001 - queue contract.
    assert handoff.payload["digested_information"] is digest


def test_task_reanalysis_replaces_one_root_overlay_and_hands_digest_to_analyzer() -> (
    None
):
    """Reanalysis keeps the root objective while replacing current-turn context."""
    session = Session()
    root = session.task_store.create_task("Root")
    root.metadata["mission"] = "Original objective."
    first = DigestedInformation(
        context_summary="First summary.", original_query="First follow-up."
    )
    second = DigestedInformation(
        context_summary="Latest summary.",
        key_points=["Latest fact."],
        known_gaps=["Latest gap."],
        original_query="Latest follow-up.",
    )
    queue = NodeQueue(items=[_worker(session, first)])
    queue.current.on_complete(queue, _decision("task_reanalysis"))
    queue = NodeQueue(items=[_worker(session, second)])

    queue.current.on_complete(queue, _decision("task_reanalysis"))

    assert root.metadata["mission"] == "Original objective."
    assert root.metadata["current_context_overlay"]["context_summary"] == (
        "Latest summary."
    )
    assert "First summary." not in str(root.metadata["current_context_overlay"])
    analyzer = queue.items[1]
    handoff = queue._inputs[analyzer.node_id]  # noqa: SLF001 - queue contract.
    assert handoff.payload["digested_information"] is second


def test_proceed_execution_replaces_overlay_and_skips_reanalysis_nodes() -> None:
    """Execution receives the new compact context without rebuilding the roadmap."""
    session = Session()
    root = session.task_store.create_task("Root")
    digest = DigestedInformation(
        context_summary="Execute this latest change.", original_query="Apply it now."
    )
    worker = _worker(session, digest)
    queue = NodeQueue(items=[worker])

    worker.on_complete(queue, _decision("proceed_execution"))

    assert root.metadata["current_context_overlay"]["context_summary"] == (
        "Execute this latest change."
    )
    assert [node.node_id for node in queue.items] == [
        "worker",
        "task_executor",
        "result_reviewer",
    ]


def test_passthrough_leaves_existing_task_context_unchanged() -> None:
    """A non-worker response must not replace context or schedule task nodes."""
    session = Session()
    root = session.task_store.create_task("Root")
    root.metadata["current_context_overlay"] = {"context_summary": "Earlier turn."}
    worker = _worker(
        session,
        DigestedInformation(context_summary="Ignored turn.", original_query="Hello."),
    )
    queue = NodeQueue(items=[worker])

    worker.on_complete(queue, _decision("passthrough"))

    assert queue.items == [worker]
    assert (
        root.metadata["current_context_overlay"]["context_summary"] == "Earlier turn."
    )
