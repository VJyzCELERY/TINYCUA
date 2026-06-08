"""RouteMap — lightweight dispatch table for DecisionNode routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tinycua.loops.node import DecisionResult
    from tinycua.loops.node_queue import NodeQueue

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """A single route entry in the RouteMap.

    Attributes:
        label: The classification label this route handles.
        handler: Callable that executes when this route is dispatched.
    """

    label: str
    handler: Callable[[NodeQueue, DecisionResult], None]


class RouteMap:
    """Lightweight dispatch table for DecisionNode routing.

    Maps validated classification labels to route handler callables.
    Each concrete DecisionNode can have its own RouteMap instance.

    Usage:
        route_map = RouteMap()
        route_map.register("worker", handle_worker)
        route_map.dispatch("worker", queue, result)
    """

    def __init__(self) -> None:
        """Initialize the route map."""
        self.routes: dict[str, Route] = {}

    def register(self, label: str, handler: Callable[[NodeQueue, DecisionResult], None]) -> None:
        """Register a route handler for a classification label.

        Args:
            label: The classification label (e.g., "worker", "passthrough").
            handler: Callable invoked when this label is dispatched.
        """
        self.routes[label] = Route(label=label, handler=handler)
        logger.debug("route_map registered label=%s", label)

    def dispatch(self, label: str, queue: NodeQueue, result: DecisionResult) -> None:
        """Dispatch to the handler for the given label.

        Args:
            label: The classification label to dispatch.
            queue: The node queue (may be mutated by handler).
            result: The decision result from classification.

        Raises:
            ValueError: If label is not registered in the route map.
        """
        if not self.has_route(label):
            msg = f"Unknown route label: {label!r}. Registered: {list(self.routes.keys())}"
            raise ValueError(msg)

        route = self.routes[label]
        logger.info("route_map dispatch label=%s", label)
        route.handler(queue, result)

    def has_route(self, label: str) -> bool:
        """Check if a label is registered.

        Args:
            label: The classification label to check.

        Returns:
            True if the label is registered, False otherwise.
        """
        return label in self.routes
