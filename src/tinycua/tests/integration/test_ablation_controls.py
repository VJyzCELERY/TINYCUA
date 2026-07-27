"""Contracts for Information Digester and Result Reviewer ablations."""

from __future__ import annotations

from pathlib import Path

import pytest

from tinycua.config.node_config import NodeConfigBase, create_node_config
from tinycua.config.session_config import InteractionPolicy, SessionConfig
from tinycua.config.types import LLMResult
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node import DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.node_input import NodeInput
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session
from tinycua.models.session_context_entry import append_output_entry, entry_content
from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus
from tests.integration.test_runtime_invariant_route_matrix import _RouteMatrixScript


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


class _LLMCallTrace:
    """Record the runtime's concrete node-to-LLM dispatches."""

    def __init__(self) -> None:
        self.node_ids: list[str] = []
        self.messages_by_node: dict[str, list[list[dict]]] = {}

    def on_before_node_call(
        self,
        node_id: str,
        _session_id: str,
        _attempt: int,
        _messages: list[dict],
        _resolved_tools: list,
    ) -> None:
        self.node_ids.append(node_id)
        self.messages_by_node.setdefault(node_id, []).append(_messages)

    def on_after_node_call(
        self,
        _node_id: str,
        _session_id: str,
        _attempt: int,
        _result: LLMResult,
        _validation: object,
    ) -> None:
        return None


def _scripted_agent(
    tmp_path: Path,
    *,
    digest_enabled: bool,
    review_enabled: bool,
    route: str = "worker",
    worker_route: str = "task_creation",
    interaction_policy: InteractionPolicy | None = None,
    session: Session | None = None,
):
    """Build a full loop backed by the deterministic route-matrix script."""
    config = SessionConfig(
        workspace_dir=tmp_path,
        digest_enabled=digest_enabled,
        review_enabled=review_enabled,
        interaction_policy=interaction_policy or InteractionPolicy(),
    )
    session = session or Session(session_config=config)
    session.session_config = config
    script = _RouteMatrixScript(route=route, worker_route=worker_route)
    agent = create_tinycua_agent(
        session=session,
        session_config=config,
        enable_native_tools=True,
    )
    agent._call_llm = script  # type: ignore[method-assign]
    llm_calls = _LLMCallTrace()
    agent.loop.agent_monitor = llm_calls
    return agent, script, llm_calls


def _trace_node_ids(agent: object) -> list[str]:
    """Return started node ids from a completed scripted runtime."""
    return [entry["node_id"] for entry in agent.loop.get_execution_trace()]  # type: ignore[attr-defined]


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


def test_no_review_executor_completion_advances_before_scheduling_retry_or_next_task() -> (
    None
):
    """No-review executor completion never leaves a duplicate executor queued."""
    session = Session(session_config=SessionConfig(review_enabled=False))
    store = session.task_store
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    store.create_task("Next", parent_id=root.task_id)

    for result in (
        TaskResult(content="failed", success=False),
        TaskResult(content="done", success=True),
    ):
        store.record_result(active.task_id, result)
        executor = TinyCUATaskExecutorNode(
            "task_executor", create_node_config("task_executor")
        )
        executor.ensure_session(session)
        queue = NodeQueue(items=[executor])

        executor.on_complete(queue, LLMResult())

        assert queue.current is not executor
        assert [node.node_id for node in queue.items] == ["task_executor"]
        assert all(node.node_id != "result_reviewer" for node in queue.items)


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("digest_enabled", "review_enabled"),
    [(True, True), (False, True), (True, False), (False, False)],
)
async def test_ablation_trace_runs_all_four_component_combinations(
    tmp_path: Path, digest_enabled: bool, review_enabled: bool
) -> None:
    """Each condition starts and calls exactly its enabled optional nodes."""
    agent, _script, llm_calls = _scripted_agent(
        tmp_path,
        digest_enabled=digest_enabled,
        review_enabled=review_enabled,
    )

    await agent.run("Build a note-taking app")

    node_ids = _trace_node_ids(agent)
    assert ("digester" in node_ids) is digest_enabled
    assert ("digester" in llm_calls.node_ids) is digest_enabled
    assert ("result_reviewer" in node_ids) is review_enabled
    assert ("result_reviewer" in llm_calls.node_ids) is review_enabled


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route", "interaction_policy", "prior_digest"),
    [
        ("worker", InteractionPolicy(), False),
        ("uncertain", InteractionPolicy(uncertain_strategy="route_worker"), False),
        ("worker", InteractionPolicy(), True),
    ],
    ids=["worker", "uncertain-worker", "redigestion"],
)
async def test_ablation_trace_no_digest_query_entries_never_start_or_call_digester(
    tmp_path: Path,
    route: str,
    interaction_policy: InteractionPolicy,
    prior_digest: bool,
) -> None:
    """Normal, uncertain, and redigestion entries bypass the digester."""
    config = SessionConfig(digest_enabled=False, review_enabled=False)
    session = Session(session_config=config)
    if prior_digest:
        append_output_entry(
            session, DigestedInformation(original_query="Old"), "digester"
        )
    agent, _script, llm_calls = _scripted_agent(
        tmp_path,
        digest_enabled=False,
        review_enabled=False,
        route=route,
        interaction_policy=interaction_policy,
        session=session,
    )

    await agent.run("Latest request")

    assert "worker" in _trace_node_ids(agent)
    assert "digester" not in _trace_node_ids(agent)
    assert "digester" not in llm_calls.node_ids
    assert sum(
        isinstance(entry_content(entry), DigestedInformation)
        for entry in session.session_context
    ) == int(prior_digest)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("worker_route", "target_node"),
    [
        ("task_creation", "task_create"),
        ("task_recreation", "task_create"),
        ("task_reanalysis", "task_analyzer"),
        ("proceed_execution", "task_executor"),
    ],
)
@pytest.mark.parametrize("digest_enabled", [True, False])
async def test_ablation_trace_worker_routes_preserve_component_boundary(
    tmp_path: Path,
    digest_enabled: bool,
    worker_route: str,
    target_node: str,
) -> None:
    """Worker routes retain their target while disabled digestion starts no node."""
    config = SessionConfig(digest_enabled=digest_enabled, review_enabled=False)
    session = Session(session_config=config)
    if worker_route == "task_recreation":
        session.task_store.create_task(
            "Completed prior task"
        ).status = TaskStatus.COMPLETED
    elif worker_route in {"task_reanalysis", "proceed_execution"}:
        root = session.task_store.create_task("Existing task")
        session.task_store.create_task("Active task", parent_id=root.task_id)
        root.metadata["current_context_overlay"] = {"context_summary": "Earlier"}
    agent, _script, llm_calls = _scripted_agent(
        tmp_path,
        digest_enabled=digest_enabled,
        review_enabled=False,
        worker_route=worker_route,
        session=session,
    )

    await agent.run("Latest request")

    node_ids = _trace_node_ids(agent)
    worker_index = node_ids.index("worker")
    assert node_ids[worker_index + 1] == target_node
    assert ("digester" in node_ids) is digest_enabled
    assert ("digester" in llm_calls.node_ids) is digest_enabled
    if not digest_enabled:
        assert "Latest request" in str(llm_calls.messages_by_node[target_node])


@pytest.mark.asyncio
@pytest.mark.parametrize("digest_enabled", [True, False])
async def test_ablation_trace_response_require_digest_respects_control(
    tmp_path: Path, digest_enabled: bool
) -> None:
    """A require-digest response suspends only in the full-control condition."""
    agent, _script, llm_calls = _scripted_agent(
        tmp_path,
        digest_enabled=digest_enabled,
        review_enabled=False,
        route="passthrough",
    )
    response = agent.loop.queue.items[-1]
    response.config.metadata["require_digest"] = True
    agent.loop.queue_factory = None

    await agent.run("Answer directly")

    assert ("digester" in _trace_node_ids(agent)) is digest_enabled
    assert ("digester" in llm_calls.node_ids) is digest_enabled
