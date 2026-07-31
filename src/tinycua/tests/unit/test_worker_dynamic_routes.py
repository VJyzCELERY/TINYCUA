"""Dynamic worker route option contracts."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.task import TaskStatus


def _worker_route_enum(loop: TinyCUALoop, worker: TinyCUAWorkerNode) -> list[str]:
    """Return the select_worker_route enum exposed to the model."""
    worker.ensure_session(loop.root_session)
    _messages, tools = loop._prepare_node(worker, [], None)
    route_tool = next(tool for tool in tools if tool.name == "select_worker_route")
    return route_tool.parameters["properties"]["route"]["enum"]


def test_worker_with_no_task_exposes_only_task_creation_route() -> None:
    """Without task state, WorkerNode must not show impossible task routes."""
    loop = TinyCUALoop()
    worker = TinyCUAWorkerNode("worker", create_node_config("worker"))

    assert _worker_route_enum(loop, worker) == ["task_creation"]
    assert worker.should_run_deterministically()
    assert (
        worker.run_deterministic(NodeQueue(items=[worker])).tool_calls[0]["function"][
            "arguments"
        ]
        == '{"route":"task_creation"}'
    )


def test_worker_with_existing_task_exposes_stateful_execution_routes() -> None:
    """Existing task state enables reanalysis/recreation/proceed choices."""
    loop = TinyCUALoop()
    loop.root_session.task_store.create_task("Existing task")
    worker = TinyCUAWorkerNode("worker", create_node_config("worker"))

    routes = _worker_route_enum(loop, worker)

    assert "task_creation" not in routes
    assert {
        "task_recreation",
        "task_reanalysis",
        "proceed_execution",
        "passthrough",
    }.issubset(routes)


def test_worker_rejects_impossible_initial_route_tool_call() -> None:
    """A model that ignores the route enum should retry, not crash on dispatch."""
    loop = TinyCUALoop()
    worker = TinyCUAWorkerNode("worker", create_node_config("worker"))
    worker.ensure_session(loop.root_session)
    worker.refresh_route_options()

    validation = loop._validate_node_result(
        worker,
        LLMResult(
            tool_calls=[
                {
                    "type": "function",
                    "function": {
                        "name": "select_worker_route",
                        "arguments": '{"route":"passthrough"}',
                    },
                }
            ]
        ),
    )

    assert not validation.is_valid
    assert "task_creation" in "; ".join(validation.errors)


def test_worker_with_terminal_root_offers_only_recreation_or_passthrough() -> None:
    """Finished work cannot be executed or reanalyzed as if it were active."""
    loop = TinyCUALoop()
    root = loop.root_session.task_store.create_task("Finished task")
    root.status = TaskStatus.COMPLETED
    worker = TinyCUAWorkerNode("worker", create_node_config("worker"))

    assert _worker_route_enum(loop, worker) == ["task_recreation", "passthrough"]
