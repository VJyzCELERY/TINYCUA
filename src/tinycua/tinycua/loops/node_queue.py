"""NodeQueue for sequential execution with terminal safety guarantees.

Manages the graph of execution nodes with support for:
- Sequential advancement through nodes
- Dynamic queue mutation (spawn, clear)
- Terminal safety invariant enforcement
- Input tracking per node
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike

_EMPTY_INPUT: NodeInputLike = cast("NodeInputLike", {})


@dataclass
class NodeQueue:
    """Sequential execution queue for TinyCUA nodes.

    Manages a list of nodes with sequential execution semantics.
    The current node is always items[0]. Supports dynamic mutation
    and terminal safety guarantees.

    Attributes:
        items: List of queued nodes (items[0] is the current node).
        _inputs: Internal mapping of node_id to input data.
    """

    items: list[Node] = field(default_factory=list)
    _inputs: dict[str, NodeInputLike] = field(default_factory=dict)

    @property
    def current(self) -> Node | None:
        """Return the current node (items[0]) or None if empty.

        Returns:
            The current node, or None if the queue is empty.
        """
        return self.items[0] if self.items else None

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if the queue has no nodes, False otherwise.
        """
        return len(self.items) == 0

    def input_for_current(self) -> NodeInputLike:
        """Get input data for the current node.

        Returns:
            The stored input for the current node, or empty dict if none.
        """
        if not self.items:
            return _EMPTY_INPUT
        return self._inputs.get(self.items[0].node_id, _EMPTY_INPUT)

    def set_input(self, node: Node, input_data: NodeInputLike) -> None:
        """Set input data for a specific node.

        Args:
            node: The node to set input for.
            input_data: The input data to associate with the node.
        """
        self._inputs[node.node_id] = input_data

    def clear_input(self, node_id: str) -> None:
        """Clear input data for a specific node.

        Removes the stored input for a node by its ID. No-op if the node
        has no stored input.

        Args:
            node_id: The ID of the node whose input should be cleared.
        """
        self._inputs.pop(node_id, None)

    def advance(self) -> Node | None:
        """Advance to the next node.

        Calls propagate() on the current node (if not already propagated),
        then removes it from the queue. Returns the new current node or None.

        Returns:
            The next node, or None if the queue becomes empty.

        Raises:
            ValueError: If the queue is empty.
        """
        if not self.items:
            msg = "Cannot advance an empty queue"
            raise ValueError(msg)

        current_node = self.items[0]

        # Call propagate() if not already propagated
        if not getattr(current_node, "_propagated", False):
            current_node.propagate()

        # Remove current node and clean up input
        self.items.pop(0)
        self._inputs.pop(current_node.node_id, None)

        return self.current

    def spawn_after_current(self, nodes: list[Node]) -> None:
        """Insert nodes after the current node.

        Args:
            nodes: List of nodes to insert after the current node.

        Raises:
            ValueError: If the queue is empty.
        """
        if not self.items:
            msg = "Cannot spawn after an empty queue"
            raise ValueError(msg)

        if not nodes:
            return

        # Insert nodes after items[0] using slice assignment
        self.items[1:1] = nodes

    def clear_after_current(self) -> None:
        """Remove all nodes after the current node.

        No-op if the queue is empty or has only one node.
        """
        if len(self.items) <= 1:
            return

        # Remove all nodes after items[0] and clean up their inputs
        nodes_to_remove = self.items[1:]
        self.items = self.items[:1]

        for node in nodes_to_remove:
            self._inputs.pop(node.node_id, None)

    def suspend_current_and_prepend(self, nodes: list[Node]) -> None:
        """Suspend the current node and prepend new nodes before it.

        Keeps the current node in the queue but inserts ``nodes`` at the
        front so the first prepended node becomes the new current.  The
        suspended node's input mapping is preserved in ``_inputs``.

        Args:
            nodes: Nodes to prepend before the suspended current node.

        Raises:
            ValueError: If the queue is empty (no current node to suspend).
        """
        if not self.items:
            msg = "Cannot suspend in an empty queue"
            raise ValueError(msg)

        if not nodes:
            return

        # Do NOT call propagate() — the node is suspended, not completed.
        # Prepend nodes before items[0] using slice assignment.
        self.items[0:0] = nodes

    def add_front(self, node: Node) -> None:
        """Add a node to the front of the queue with deduplication check.

        Handles empty queues gracefully by appending the node.

        Raises RuntimeError if a node with the same node_id already exists
        in the queue.

        Args:
            node: The node to add to the front.

        Raises:
            RuntimeError: If a node with the same node_id already exists.
        """
        for existing in self.items:
            if existing.node_id == node.node_id:
                msg = f"Node already in queue: {node.node_id}"
                raise RuntimeError(msg)
        if not self.items:
            self.items.append(node)
            return
        self.suspend_current_and_prepend([node])

    def ensure_terminal(self, default_terminal_node: Node) -> None:
        """Ensure the queue ends with a terminal node.

        Appends the default terminal node if the last node is not terminal.
        No-op if the queue is empty and the default is terminal.

        Args:
            default_terminal_node: The terminal node to append if needed.
        """
        if not self.items:
            self.items.append(default_terminal_node)
            return

        if not self.items[-1].is_terminal:
            self.items.append(default_terminal_node)

    def find_worker_spawned_nodes(self) -> list[Node]:
        """Find all nodes spawned by WorkerNode before terminal ResponseNode.

        Scans the queue for a node with node_id "worker", then collects
        all subsequent nodes until the first terminal node.

        Returns:
            List of worker-spawned nodes (empty if no worker found).
        """
        worker_idx: int | None = None
        for i, node in enumerate(self.items):
            if node.node_id == "worker":
                worker_idx = i
                break

        if worker_idx is None:
            return []

        spawned: list[Node] = []
        for node in self.items[worker_idx + 1 :]:
            if node.is_terminal:
                break
            spawned.append(node)
        return spawned

    def find_existing_worker_node(self) -> Node | None:
        """Find existing WorkerNode in queue before terminal ResponseNode.

        This is the source of truth for worker-node lookup. QueryAnalyst's
        find_existing_worker() should delegate to this method to avoid
        logic duplication.

        Returns:
            The existing worker node, or None if not found.
        """
        for node in self.items:
            if node.is_terminal:
                break
            if node.node_id == "worker":
                return node
        return None
