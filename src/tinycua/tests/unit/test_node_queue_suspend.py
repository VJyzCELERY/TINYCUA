"""Unit tests for NodeQueue suspension and prepend."""

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


class TestSuspendBasic:
    """Tests for basic suspend_current_and_prepend behavior."""

    def test_suspend_keeps_current_queued_and_prepends_before_it(self):
        """suspend_current_and_prepend() keeps current node queued,
        inserts new nodes before it, and makes first prepended node current."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a, node_b]

        queue.suspend_current_and_prepend([node_c])

        assert queue.items == [node_c, node_a, node_b]
        assert queue.current is node_c

    def test_suspend_with_single_node(self):
        """suspend_current_and_prepend([NodeB]) on [NodeA] yields [NodeB, NodeA]."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]

        queue.suspend_current_and_prepend([node_b])

        assert queue.items == [node_b, node_a]
        assert queue.current is node_b

    def test_suspend_with_multiple_nodes(self):
        """suspend_current_and_prepend([NodeC, NodeD]) on [NodeA, NodeB]
        yields [NodeC, NodeD, NodeA, NodeB]."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        node_d = _make_node("d")
        queue.items = [node_a, node_b]

        queue.suspend_current_and_prepend([node_c, node_d])

        assert queue.items == [node_c, node_d, node_a, node_b]
        assert queue.current is node_c

    def test_suspend_empty_list_is_noop(self):
        """suspend_current_and_prepend([]) is a no-op."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.suspend_current_and_prepend([])

        assert queue.items == [node_a]
        assert queue.current is node_a

    def test_suspend_empty_queue_raises_value_error(self):
        """suspend_current_and_prepend() on empty queue raises ValueError."""
        queue = NodeQueue()
        with pytest.raises(ValueError, match="Cannot suspend in an empty queue"):
            queue.suspend_current_and_prepend([_make_node("x")])


class TestSuspendPropagation:
    """Tests for propagation behavior during suspension."""

    def test_suspend_does_not_call_propagate(self):
        """suspend_current_and_prepend() does NOT call propagate() on suspended node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        queue.items = [node_a]

        queue.suspend_current_and_prepend([_make_node("b")])

        node_a.propagate.assert_not_called()


class TestSuspendInputPreservation:
    """Tests for input mapping preservation during suspension."""

    def test_suspend_preserves_input_mapping(self):
        """Suspended node's input mapping is preserved after suspension."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]
        queue.set_input(node_a, {"query": "test"})

        queue.suspend_current_and_prepend([node_b])

        assert queue._inputs.get("a") == {"query": "test"}

    def test_suspend_prepended_node_input_lifecycle(self):
        """Prepended node can have input assigned and is cleaned up on advance."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]
        queue.set_input(node_a, {"original": "data"})

        queue.suspend_current_and_prepend([node_b])
        queue.set_input(node_b, {"prepended": "input"})

        assert queue.input_for_current() == {"prepended": "input"}

        queue.advance()
        assert "b" not in queue._inputs

        assert queue.current is node_a
        assert queue._inputs.get("a") is not None

    def test_suspend_preserves_suspended_input_after_prepended_advance(self):
        """Suspended node's input is preserved and prepended node's input is
        cleaned up when advance() removes the prepended node."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]
        queue.set_input(node_a, {"query": "original"})

        queue.suspend_current_and_prepend([node_b])
        queue.set_input(node_b, {"task": "digest"})

        queue.advance()

        node_b.propagate.assert_not_called()

        assert queue.current is node_a
        assert queue._inputs.get("a") == {"query": "original"}
        assert "b" not in queue._inputs


class TestSuspendResume:
    """Tests for resume behavior after suspension."""

    def test_suspend_resume_after_advance(self):
        """Suspended node resumes when prepended node completes and advance() is called."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        queue.items = [node_a]

        queue.suspend_current_and_prepend([node_b])
        assert queue.current is node_b

        queue.advance()

        assert queue.current is node_a


class TestSuspendNested:
    """Tests for nested suspension scenarios."""

    def test_suspend_nested_suspension_queue_state(self):
        """Nested suspensions: NodeA suspends for [NodeB], then NodeB suspends for [NodeC].
        Queue becomes [NodeC, NodeB, NodeA] with NodeC as current."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_c = _make_node("c")
        queue.items = [node_a]

        queue.suspend_current_and_prepend([node_b])
        assert queue.items == [node_b, node_a]
        assert queue.current is node_b

        queue.suspend_current_and_prepend([node_c])
        assert queue.items == [node_c, node_b, node_a]
        assert queue.current is node_c


class TestSuspendClearAfterCurrent:
    """Tests for clear_after_current interaction with suspended nodes."""

    def test_clear_after_current_with_suspended_node(self):
        """clear_after_current() removes nodes after current. If suspended node
        is at items[1] (after current), it IS cleared."""
        queue = NodeQueue()
        node_a = _make_node("a")
        node_b = _make_node("b")
        node_d = _make_node("d")
        queue.items = [node_a, node_b]
        queue.suspend_current_and_prepend([node_d])
        queue.clear_after_current()

        assert queue.items == [node_d]
