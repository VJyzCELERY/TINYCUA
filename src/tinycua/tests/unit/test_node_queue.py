"""Integration tests for NodeQueue basic execution and terminal safety."""

import pytest
from unittest.mock import MagicMock
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import Node


def _make_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock(spec=Node)
    node.node_id = node_id
    node.is_terminal = is_terminal
    node.propagate = MagicMock()
    return node


class TestNodeQueueCurrent:
    """Tests for current property."""

    def test_current_returns_first_node(self):
        """queue.current returns items[0] when present."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]
        assert queue.current is node_a

    def test_current_returns_none_when_empty(self):
        """queue.current returns None when queue is empty."""
        queue = NodeQueue()
        assert queue.current is None


class TestNodeQueueIsEmpty:
    """Tests for is_empty()."""

    def test_is_empty_returns_true_when_empty(self):
        """is_empty() returns True when items is empty."""
        queue = NodeQueue()
        assert queue.is_empty() is True

    def test_is_empty_returns_false_when_not_empty(self):
        """is_empty() returns False when items has nodes."""
        queue = NodeQueue()
        queue.items = [_make_node("a")]
        assert queue.is_empty() is False


class TestNodeQueueAdvance:
    """Tests for advance()."""

    def test_advance_removes_current_node(self):
        """advance() removes items[0] after calling propagate()."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a, node_b]

        result = queue.advance()

        node_a.propagate.assert_called_once()
        assert result is node_b
        assert queue.items == [node_b]

    def test_advance_returns_none_when_queue_becomes_empty(self):
        """advance() returns None when queue becomes empty after removal."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        result = queue.advance()

        assert result is None
        assert queue.is_empty()

    def test_advance_raises_on_empty_queue(self):
        """advance() raises ValueError on empty queue."""
        queue = NodeQueue()
        with pytest.raises(ValueError, match="Cannot advance an empty queue"):
            queue.advance()

    def test_advance_calls_propagate_before_removal(self):
        """advance() calls propagate() before removing the node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.advance()

        node_a.propagate.assert_called_once()

    def test_advance_skips_propagation_if_already_propagated(self):
        """advance() skips propagate() if node has _propagated flag set."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_a._propagated = True
        queue.items = [node_a]

        queue.advance()

        node_a.propagate.assert_not_called()


class TestNodeQueueSpawn:
    """Tests for spawn_after_current()."""

    def test_spawn_inserts_after_current(self):
        """spawn_after_current() inserts nodes after items[0]."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a, node_b]

        queue.spawn_after_current([node_c])

        assert queue.items == [node_a, node_c, node_b]
        assert queue.current is node_a

    def test_spawn_does_not_change_current(self):
        """spawn_after_current() does not change current node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]

        queue.spawn_after_current([node_b])

        assert queue.current is node_a

    def test_spawn_raises_on_empty_queue(self):
        """spawn_after_current() raises ValueError on empty queue."""
        queue = NodeQueue()
        with pytest.raises(ValueError, match="Cannot spawn after an empty queue"):
            queue.spawn_after_current([_make_node("x")])

    def test_spawn_with_empty_list_is_noop(self):
        """spawn_after_current([]) is a no-op."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.spawn_after_current([])

        assert queue.items == [node_a]

    def test_spawn_preserves_subsequent_nodes(self):
        """spawn_after_current() shifts existing nodes, does not overwrite."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a, node_b, node_c]
        new_node = _make_node("new")

        queue.spawn_after_current([new_node])

        assert queue.items == [node_a, new_node, node_b, node_c]


class TestNodeQueueClear:
    """Tests for clear_after_current()."""

    def test_clear_removes_nodes_after_current(self):
        """clear_after_current() removes all nodes after items[0]."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a, node_b, node_c]

        queue.clear_after_current()

        assert queue.items == [node_a]

    def test_clear_is_noop_when_only_current(self):
        """clear_after_current() is a no-op when only one node exists."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.clear_after_current()

        assert queue.items == [node_a]

    def test_clear_is_noop_when_empty(self):
        """clear_after_current() is a no-op when queue is empty."""
        queue = NodeQueue()
        queue.clear_after_current()
        assert queue.is_empty()


class TestNodeQueueEnsureTerminal:
    """Tests for ensure_terminal()."""

    def test_ensure_terminal_appends_when_no_terminal(self):
        """ensure_terminal() appends default when last node is not terminal."""
        queue = NodeQueue()
        node_a = _make_node("a", is_terminal=False)
        node_b = _make_node("b", is_terminal=False)
        queue.items = [node_a, node_b]
        terminal = _make_node("response", is_terminal=True)

        queue.ensure_terminal(terminal)

        assert queue.items == [node_a, node_b, terminal]

    def test_ensure_terminal_noop_when_terminal_exists(self):
        """ensure_terminal() is a no-op when last node is terminal."""
        queue = NodeQueue()
        node_a = _make_node("a", is_terminal=False)
        terminal = _make_node("response", is_terminal=True)
        queue.items = [node_a, terminal]
        default = _make_node("default_response", is_terminal=True)

        queue.ensure_terminal(default)

        assert queue.items == [node_a, terminal]

    def test_ensure_terminal_appends_to_empty_queue(self):
        """ensure_terminal() appends to empty queue."""
        queue = NodeQueue()
        terminal = _make_node("response", is_terminal=True)

        queue.ensure_terminal(terminal)

        assert queue.items == [terminal]


class TestNodeQueueInputTracking:
    """Tests for input_for_current() and set_input()."""

    def test_input_for_current_returns_stored_input(self):
        """input_for_current() returns stored input for current node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]
        queue.set_input(node_a, {"query": "test"})

        assert queue.input_for_current() == {"query": "test"}

    def test_input_for_current_returns_empty_when_no_input(self):
        """input_for_current() returns empty dict when no input is set."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        assert queue.input_for_current() == {}

    def test_input_for_current_returns_empty_when_empty_queue(self):
        """input_for_current() returns empty dict when queue is empty."""
        queue = NodeQueue()
        assert queue.input_for_current() == {}
