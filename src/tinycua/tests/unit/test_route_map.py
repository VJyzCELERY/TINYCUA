"""Unit tests for RouteMap."""

from __future__ import annotations

import pytest

from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.route_map import Route, RouteMap


def test_route_map_register():
    """RouteMap.register adds a route for the given label."""
    # Arrange
    route_map = RouteMap()

    def handler(queue: NodeQueue, result: DecisionResult) -> None:
        pass

    # Act
    route_map.register("worker", handler)

    # Assert
    assert "worker" in route_map.routes
    assert route_map.routes["worker"].label == "worker"
    assert route_map.routes["worker"].handler is handler


def test_route_map_dispatch_calls_handler():
    """RouteMap.dispatch calls the registered handler with queue and result."""
    # Arrange
    route_map = RouteMap()
    called_args: list[tuple[NodeQueue, DecisionResult]] = []

    def handler(queue: NodeQueue, result: DecisionResult) -> None:
        called_args.append((queue, result))

    route_map.register("worker", handler)
    queue = NodeQueue()
    result = DecisionResult(
        route_label="worker",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="worker", role="assistant"),
    )

    # Act
    route_map.dispatch("worker", queue, result)

    # Assert
    assert len(called_args) == 1
    assert called_args[0][0] is queue
    assert called_args[0][1] is result


def test_route_map_dispatch_unknown_label():
    """RouteMap.dispatch raises ValueError for unknown labels."""
    # Arrange
    route_map = RouteMap()
    queue = NodeQueue()
    result = DecisionResult(
        route_label="unknown",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="unknown", role="assistant"),
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Unknown route label"):
        route_map.dispatch("unknown", queue, result)


def test_route_map_has_route():
    """RouteMap.has_route returns True for registered labels."""
    # Arrange
    route_map = RouteMap()

    def handler(queue: NodeQueue, result: DecisionResult) -> None:
        pass

    route_map.register("worker", handler)

    # Assert
    assert route_map.has_route("worker") is True
    assert route_map.has_route("passthrough") is False


def test_route_dataclass():
    """Route dataclass stores label and handler."""
    # Arrange
    def handler(queue: NodeQueue, result: DecisionResult) -> None:
        pass

    # Act
    route = Route(label="worker", handler=handler)

    # Assert
    assert route.label == "worker"
    assert route.handler is handler
