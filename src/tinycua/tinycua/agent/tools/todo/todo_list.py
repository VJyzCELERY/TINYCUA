"""Todo list tool.

Provides the ``TodoList`` class and the ``todo_list`` tool for managing
an executor-local todo list. Supports add, list, update, and clear
operations via a single ``command`` parameter.

When used through ``register_all()``, the tool is bound to the
``ExecutorContext``'s todo list, enabling shared state across tools.
When used standalone, a module-level ``TodoList`` singleton is used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua_sdk.tools.decorators import Tool, tool

if TYPE_CHECKING:
    from tinycua.agent.tools.context import ExecutorContext

# ---------------------------------------------------------------------------
# TodoList class
# ---------------------------------------------------------------------------

_TODO_ITEM_FIELDS = frozenset({"id", "item", "status"})
_VALID_STATUSES = frozenset({"pending", "completed"})


class TodoList:
    """An in-memory todo list with add/list/update/clear operations.

    Items are stored as dicts: ``{"id": int, "item": str, "status": str}``.
    IDs are auto-incrementing and never reused (even after ``clear()``).
    """

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._next_id: int = 1

    def add(self, item: str) -> int:
        """Add a new todo item and return its id."""
        item_id = self._next_id
        self._next_id += 1
        self._items.append({"id": item_id, "item": item, "status": "pending"})
        return item_id

    def list_items(self) -> list[dict[str, Any]]:
        """Return all todo items (a copy of the internal list)."""
        return list(self._items)

    def update(self, item_id: int, status: str) -> bool:
        """Update the status of an existing item.

        Args:
            item_id: The id of the item to update.
            status: New status (``"pending"`` or ``"completed"``).

        Returns:
            ``True`` on success.

        Raises:
            ValueError: If *item_id* is not found or *status* is invalid.
        """
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"Invalid status: '{status}'. Valid: {sorted(_VALID_STATUSES)}",
            )
        for entry in self._items:
            if entry["id"] == item_id:
                entry["status"] = status
                return True
        raise ValueError(f"Todo item not found: id={item_id}")

    def clear(self) -> int:
        """Remove all items and return the number cleared."""
        count = len(self._items)
        self._items.clear()
        return count

    def reset(self) -> None:
        """Reset the list to its initial empty state (for testing)."""
        self._items.clear()
        self._next_id = 1


# ---------------------------------------------------------------------------
# Module-level singleton (used when the tool is imported directly)
# ---------------------------------------------------------------------------

_DEFAULT_TODO: TodoList = TodoList()


def _route_command(
    todo: TodoList,
    command: str,
    item: str | None = None,
    item_id: int | None = None,
    status: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Route a todo command to the appropriate *TodoList* method."""
    if command == "add":
        if item is None:
            return {"error": "Missing required argument: 'item' for command 'add'"}
        new_id = todo.add(item)
        return {"success": True, "id": new_id, "item": item}
    elif command == "list":
        return todo.list_items()
    elif command == "update":
        if item_id is None:
            return {"error": "Missing required argument: 'item_id' for command 'update'"}
        if status is None:
            return {"error": "Missing required argument: 'status' for command 'update'"}
        try:
            todo.update(item_id, status)
            return {"success": True, "id": item_id, "status": status}
        except ValueError as e:
            return {"error": str(e)}
    elif command == "clear":
        cleared = todo.clear()
        return {"success": True, "cleared_count": cleared}
    else:
        return {
            "error": f"Unknown todo command: '{command}'. Valid: add, list, update, clear",
        }


@tool
def todo_list(
    command: str,
    item: str | None = None,
    item_id: int | None = None,
    status: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Manage the executor-local todo list.

    Commands:
    - **add** (item): Add a new todo item.
      Returns ``{"success": true, "id": 1, "item": "..."}``
    - **list**: List all items.
      Returns ``[{"id": 1, "item": "...", "status": "pending"}, ...]``
    - **update** (item_id, status): Update an item's status to ``"pending"``
      or ``"completed"``.
      Returns ``{"success": true, "id": 1, "status": "completed"}``
    - **clear**: Remove all items.
      Returns ``{"success": true, "cleared_count": 5}``

    Args:
        command: The operation to perform: ``"add"``, ``"list"``,
            ``"update"``, or ``"clear"``.
        item: The todo item text (required for ``"add"``).
        item_id: The id of the item (required for ``"update"``).
        status: New status for the item (required for ``"update"``).

    Returns:
        A dict or list depending on the command.
    """
    return _route_command(_DEFAULT_TODO, command, item, item_id, status)


# ---------------------------------------------------------------------------
# Context-aware factory
# ---------------------------------------------------------------------------


def create_todo_list(context: ExecutorContext) -> Tool:
    """Create a ``todo_list`` tool bound to the given *context*.

    The returned tool uses ``context.get_todo_list()`` for state, so
    all tools sharing the same context share the same todo list.
    """
    def _execute(
        command: str,
        item: str | None = None,
        item_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        todo = context.get_todo_list()
        return _route_command(todo, command, item, item_id, status)

    return Tool.from_callable(_execute, name="todo_list")


def reset_default_todo() -> None:
    """Reset the module-level todo list singleton (for testing)."""
    global _DEFAULT_TODO
    _DEFAULT_TODO = TodoList()


__all__ = [
    "TodoList",
    "create_todo_list",
    "reset_default_todo",
    "todo_list",
]
