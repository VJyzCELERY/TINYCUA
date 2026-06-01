"""Unit tests for TodoList and todo_list tool."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# TodoList class unit tests
# ---------------------------------------------------------------------------


class TestTodoList:
    """Test the TodoList class directly."""

    def test_add_item(self):
        """Adding an item should return the assigned id."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        assert todo.add("First task") == 1
        assert todo.add("Second task") == 2

    def test_list_empty(self):
        """A new TodoList should have no items."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        assert todo.list_items() == []

    def test_list_with_items(self):
        """Listing should return all items in order."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        todo.add("Task A")
        todo.add("Task B")

        items = todo.list_items()
        assert len(items) == 2
        assert items[0] == {"id": 1, "item": "Task A", "status": "pending"}
        assert items[1] == {"id": 2, "item": "Task B", "status": "pending"}

    def test_add_duplicate_item_text(self):
        """Adding the same text twice should create separate items."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        todo.add("Same task")
        todo.add("Same task")

        items = todo.list_items()
        assert len(items) == 2
        assert items[0]["id"] == 1
        assert items[1]["id"] == 2

    def test_update_status(self):
        """Updating an item's status should work."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        todo.add("Task to complete")

        result = todo.update(1, "completed")
        assert result is True

        items = todo.list_items()
        assert items[0]["status"] == "completed"

    def test_update_nonexistent_item(self):
        """Updating a non-existent item should raise ValueError."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        with pytest.raises(ValueError, match="Todo item not found"):
            todo.update(999, "completed")

    def test_update_invalid_status(self):
        """Updating with an invalid status should raise ValueError."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        todo.add("Test")
        with pytest.raises(ValueError, match="Invalid status"):
            todo.update(1, "invalid_status")

    def test_clear(self):
        """Clearing should remove all items."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        todo.add("Task A")
        todo.add("Task B")

        count = todo.clear()
        assert count == 2
        assert todo.list_items() == []

    def test_clear_empty(self):
        """Clearing an empty list should return 0."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        assert todo.clear() == 0

    def test_incremental_ids_after_clear(self):
        """IDs should continue incrementing after clear (not reset)."""
        from tinycua.agent.tools.todo.todo_list import TodoList

        todo = TodoList()
        todo.add("Old task")
        todo.clear()
        new_id = todo.add("New task")
        # IDs should not reset — next id should be 2
        assert new_id == 2


# ---------------------------------------------------------------------------
# todo_list tool integration unit tests (via @tool decorator)
# ---------------------------------------------------------------------------


class TestTodoListTool:
    """Test the @tool-decorated todo_list function."""

    def setup_method(self) -> None:
        """Reset the singleton before each test."""
        from tinycua.agent.tools.todo.todo_list import reset_default_todo
        reset_default_todo()

    def test_tool_add(self):
        """todo_list tool add command works."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        result = todo_list(command="add", item="A task")
        assert result["success"] is True
        assert result["id"] == 1
        assert result["item"] == "A task"

    def test_tool_add_empty_item(self):
        """Adding an empty item should still work."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        result = todo_list(command="add", item="")
        assert result["success"] is True

    def test_tool_add_missing_item(self):
        """Adding without item should return error."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        result = todo_list(command="add")
        assert "error" in result

    def test_tool_list_after_add(self):
        """Listing should show added items."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        todo_list(command="add", item="Task 1")
        todo_list(command="add", item="Task 2")
        items = todo_list(command="list")
        assert len(items) == 2
        # IDs are deterministic because each test gets a fresh module state
        # (but the same process may have residual state from prior tests)
        # So we just check basic shape
        for item in items:
            assert "id" in item
            assert "item" in item
            assert "status" in item

    def test_tool_update(self):
        """Updating an item works."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        todo_list(command="add", item="Test")
        result = todo_list(command="update", item_id=1, status="completed")
        assert result["success"] is True
        assert result["id"] == 1
        assert result["status"] == "completed"

    def test_tool_update_nonexistent(self):
        """Updating a non-existent item returns error."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        result = todo_list(command="update", item_id=999, status="completed")
        assert "error" in result

    def test_tool_update_invalid_status(self):
        """Updating with invalid status returns error."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        todo_list(command="add", item="Test")
        result = todo_list(command="update", item_id=1, status="invalid")
        assert "error" in result

    def test_tool_clear(self):
        """Clearing all items works."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        todo_list(command="add", item="Task A")
        todo_list(command="add", item="Task B")
        result = todo_list(command="clear")
        assert result["success"] is True
        assert result["cleared_count"] == 2

        items = todo_list(command="list")
        assert len(items) == 0

    def test_tool_invalid_command(self):
        """Unknown command returns error."""
        from tinycua.agent.tools.todo.todo_list import todo_list

        result = todo_list(command="unknown")
        assert "error" in result
        assert "Unknown todo command" in result["error"]
