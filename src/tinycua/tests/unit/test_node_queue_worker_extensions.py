"""Unit tests for NodeQueue extensions: find_worker_spawned_nodes, find_existing_worker_node."""

from __future__ import annotations

from unittest.mock import MagicMock
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import Node


def _make_mock_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock(spec=Node)
    node.node_id = node_id
    node.is_terminal = is_terminal
    node.propagate = MagicMock()
    return node


class TestFindWorkerSpawnedNodes:
    """Tests for NodeQueue.find_worker_spawned_nodes."""

    def test_finds_nodes_between_worker_and_terminal(self) -> None:
        """find_worker_spawned_nodes finds nodes between worker and terminal."""
        queue = NodeQueue()
        worker = _make_mock_node("worker")
        spawned = _make_mock_node("task_create")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, spawned, terminal]

        result = queue.find_worker_spawned_nodes()

        assert len(result) == 1
        assert result[0].node_id == "task_create"

    def test_returns_empty_when_no_worker(self) -> None:
        """find_worker_spawned_nodes returns empty when no worker node."""
        queue = NodeQueue()
        node_a = _make_mock_node("a")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [node_a, terminal]

        result = queue.find_worker_spawned_nodes()

        assert result == []

    def test_returns_empty_when_no_spawned(self) -> None:
        """find_worker_spawned_nodes returns empty when no spawned nodes."""
        queue = NodeQueue()
        worker = _make_mock_node("worker")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = queue.find_worker_spawned_nodes()

        assert result == []

    def test_stops_at_terminal(self) -> None:
        """find_worker_spawned_nodes stops at terminal node."""
        queue = NodeQueue()
        worker = _make_mock_node("worker")
        spawned = _make_mock_node("task_create")
        terminal = _make_mock_node("response", is_terminal=True)
        after_terminal = _make_mock_node("another")
        queue.items = [worker, spawned, terminal, after_terminal]

        result = queue.find_worker_spawned_nodes()

        assert len(result) == 1
        assert result[0].node_id == "task_create"

    def test_multiple_spawned_nodes(self) -> None:
        """find_worker_spawned_nodes returns all spawned nodes."""
        queue = NodeQueue()
        worker = _make_mock_node("worker")
        spawned1 = _make_mock_node("task_create")
        spawned2 = _make_mock_node("task_analyzer")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, spawned1, spawned2, terminal]

        result = queue.find_worker_spawned_nodes()

        assert len(result) == 2
        assert result[0].node_id == "task_create"
        assert result[1].node_id == "task_analyzer"


class TestFindExistingWorkerNode:
    """Tests for NodeQueue.find_existing_worker_node."""

    def test_finds_worker_node(self) -> None:
        """find_existing_worker_node returns the worker node."""
        queue = NodeQueue()
        worker = _make_mock_node("worker")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = queue.find_existing_worker_node()

        assert result is worker

    def test_returns_none_when_no_worker(self) -> None:
        """find_existing_worker_node returns None when no worker exists."""
        queue = NodeQueue()
        node_a = _make_mock_node("a")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [node_a, terminal]

        result = queue.find_existing_worker_node()

        assert result is None

    def test_returns_none_when_empty(self) -> None:
        """find_existing_worker_node returns None on empty queue."""
        queue = NodeQueue()
        result = queue.find_existing_worker_node()
        assert result is None

    def test_stops_at_terminal(self) -> None:
        """find_existing_worker_node stops at terminal node."""
        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        worker_after_terminal = _make_mock_node("worker")
        queue.items = [terminal, worker_after_terminal]

        result = queue.find_existing_worker_node()

        assert result is None

    def test_finds_first_worker(self) -> None:
        """find_existing_worker_node returns the first worker node."""
        queue = NodeQueue()
        worker1 = _make_mock_node("worker")
        worker2 = _make_mock_node("worker")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker1, worker2, terminal]

        result = queue.find_existing_worker_node()

        assert result is worker1
