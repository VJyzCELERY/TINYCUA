"""Todo list for plan-then-execute workflow in TinyCUA nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class TodoItem:
    """Single todo item with status and order.

    Attributes:
        description: Description of the task.
        status: Current status of the item.
        order: Auto-assigned insertion order (0-based).
        metadata: Arbitrary metadata.
    """

    description: str
    status: Literal["pending", "done"]
    order: int
    metadata: dict[str, Any] = field(default_factory=dict)


class Todo:
    """Per-session linear plan-then-execute list.

    Maintains items in insertion order with auto-assigned order values.

    Attributes:
        items: List of todo items.
        max_items: Maximum allowed items.
    """

    def __init__(self, max_items: int = 20) -> None:
        """Initialize the todo list.

        Args:
            max_items: Maximum number of items allowed.

        Raises:
            ValueError: If max_items is less than 1.
        """
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        self.items: list[TodoItem] = []
        self.max_items = max_items

    def append(self, description: str) -> None:
        """Add a new pending item at the end.

        Auto-assigns order = len(items) before append.

        Args:
            description: Description of the task.

        Raises:
            ValueError: If max_items would be exceeded.
        """
        if len(self.items) >= self.max_items:
            raise ValueError("Todo max items exceeded")

        order = len(self.items)
        self.items.append(
            TodoItem(
                description=description,
                status="pending",
                order=order,
            )
        )

    def mark_done(self, index: int) -> None:
        """Mark item at index as done.

        Args:
            index: Index of the item to mark done.

        Raises:
            IndexError: If index is invalid.
            ValueError: If item is already done.
        """
        if index < 0 or index >= len(self.items):
            raise IndexError("Invalid todo index")
        if self.items[index].status == "done":
            raise ValueError(f"Item at index {index} is already done")
        self.items[index].status = "done"

    def next_pending(self) -> TodoItem | None:
        """Return next pending item or None.

        Returns:
            The next pending item, or None if all items are done.
        """
        for item in self.items:
            if item.status == "pending":
                return item
        return None
