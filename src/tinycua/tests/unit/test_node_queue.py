"""Tests for NodeQueue placeholder."""

from tinycua.loops.node_queue import NodeQueue


def test_node_queue_is_empty():
    """NodeQueue is always empty in M1.1."""
    queue = NodeQueue()
    assert queue.is_empty() is True


def test_node_queue_current_is_none():
    """NodeQueue has no current node in M1.1."""
    queue = NodeQueue()
    assert queue.current is None


def test_node_queue_input_for_current():
    """NodeQueue returns empty dict for current input."""
    queue = NodeQueue()
    assert queue.input_for_current() == {}


def test_node_queue_advance_is_noop():
    """NodeQueue.advance() does not raise."""
    queue = NodeQueue()
    queue.advance()  # Should not raise


def test_node_queue_items_empty():
    """NodeQueue starts with empty items list."""
    queue = NodeQueue()
    assert queue.items == []
