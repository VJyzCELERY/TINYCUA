"""Unit tests for Todo and TodoItem."""

import pytest

from tinycua.models.todo import Todo, TodoItem


class TestTodoItem:
    """Tests for TodoItem dataclass."""

    def test_construction(self) -> None:
        """Test TodoItem construction."""
        item = TodoItem(
            description="Task 1",
            status="pending",
            order=0,
        )
        assert item.description == "Task 1"
        assert item.status == "pending"
        assert item.order == 0
        assert item.metadata == {}

    def test_with_metadata(self) -> None:
        """Test TodoItem with metadata."""
        item = TodoItem(
            description="Task 1",
            status="done",
            order=1,
            metadata={"priority": "high"},
        )
        assert item.metadata == {"priority": "high"}


class TestTodo:
    """Tests for Todo class."""

    def test_initialization(self) -> None:
        """Test Todo initialization."""
        todo = Todo()
        assert todo.items == []
        assert todo.max_items == 20

    def test_initialization_custom_max(self) -> None:
        """Test Todo initialization with custom max_items."""
        todo = Todo(max_items=5)
        assert todo.max_items == 5

    def test_initialization_max_items_zero_raises(self) -> None:
        """Test Todo raises ValueError when max_items is 0."""
        with pytest.raises(ValueError, match="max_items must be >= 1"):
            Todo(max_items=0)

    def test_initialization_max_items_negative_raises(self) -> None:
        """Test Todo raises ValueError when max_items is negative."""
        with pytest.raises(ValueError, match="max_items must be >= 1"):
            Todo(max_items=-1)

    def test_append(self) -> None:
        """Test appending items."""
        todo = Todo()
        todo.append("Task 1")
        todo.append("Task 2")

        assert len(todo.items) == 2
        assert todo.items[0].description == "Task 1"
        assert todo.items[0].status == "pending"
        assert todo.items[0].order == 0
        assert todo.items[1].description == "Task 2"
        assert todo.items[1].order == 1

    def test_append_max_items_exceeded(self) -> None:
        """Test append raises ValueError when max_items exceeded."""
        todo = Todo(max_items=2)
        todo.append("Task 1")
        todo.append("Task 2")

        with pytest.raises(ValueError, match="Todo max items exceeded"):
            todo.append("Task 3")

    def test_mark_done(self) -> None:
        """Test marking items as done."""
        todo = Todo()
        todo.append("Task 1")
        todo.append("Task 2")

        todo.mark_done(0)
        assert todo.items[0].status == "done"
        assert todo.items[1].status == "pending"

    def test_mark_done_already_done_raises(self) -> None:
        """Test mark_done raises ValueError when item is already done."""
        todo = Todo()
        todo.append("Task 1")
        todo.mark_done(0)
        with pytest.raises(ValueError, match="already done"):
            todo.mark_done(0)

    def test_mark_done_invalid_index(self) -> None:
        """Test mark_done with invalid index raises IndexError."""
        todo = Todo()
        todo.append("Task 1")

        with pytest.raises(IndexError, match="Invalid todo index"):
            todo.mark_done(99)

    def test_mark_done_negative_index(self) -> None:
        """Test mark_done with negative index raises IndexError."""
        todo = Todo()
        todo.append("Task 1")

        with pytest.raises(IndexError, match="Invalid todo index"):
            todo.mark_done(-1)

    def test_next_pending(self) -> None:
        """Test next_pending returns first pending item."""
        todo = Todo()
        todo.append("Task 1")
        todo.append("Task 2")
        todo.append("Task 3")

        item = todo.next_pending()
        assert item is not None
        assert item.description == "Task 1"

    def test_next_pending_after_done(self) -> None:
        """Test next_pending skips done items."""
        todo = Todo()
        todo.append("Task 1")
        todo.append("Task 2")
        todo.append("Task 3")

        todo.mark_done(0)
        item = todo.next_pending()
        assert item is not None
        assert item.description == "Task 2"

    def test_next_pending_all_done(self) -> None:
        """Test next_pending returns None when all items done."""
        todo = Todo()
        todo.append("Task 1")
        todo.append("Task 2")

        todo.mark_done(0)
        todo.mark_done(1)

        item = todo.next_pending()
        assert item is None

    def test_next_pending_empty(self) -> None:
        """Test next_pending returns None when empty."""
        todo = Todo()
        item = todo.next_pending()
        assert item is None

    def test_order_auto_assignment(self) -> None:
        """Test order is auto-assigned on append."""
        todo = Todo()
        todo.append("First")
        todo.append("Second")
        todo.append("Third")

        assert todo.items[0].order == 0
        assert todo.items[1].order == 1
        assert todo.items[2].order == 2
