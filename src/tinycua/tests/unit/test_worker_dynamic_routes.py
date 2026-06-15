"""Dynamic worker route option contracts."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker import TinyCUAWorkerNode


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


def test_worker_with_existing_task_exposes_stateful_execution_routes() -> None:
    """Existing task state enables reanalysis/recreation/proceed choices."""
    loop = TinyCUALoop()
    loop.root_session.task_store.create_task("Existing task")
    worker = TinyCUAWorkerNode("worker", create_node_config("worker"))

    routes = _worker_route_enum(loop, worker)

    assert "task_creation" not in routes
    assert {"task_recreation", "task_reanalysis", "proceed_execution", "passthrough"}.issubset(routes)
