"""Task tree node state object with DFS navigation."""

from __future__ import annotations

__all__ = ["Task"]

import dataclasses
from typing import Any, Self

from tinycua.state.base import StateObject


@dataclasses.dataclass
class Task(StateObject):
    """A single node in the task execution tree.

    Tasks form a tree structure navigated via DFS pre-order traversal.
    A task with child_tasks is a container (not executed directly); a task
    with child_tasks=None is a leaf (executable).

    The finished flag propagates upward: a container task can only be marked
    finished when all its children are finished, ensuring no orphaned subtasks.

    Root tasks are identified by parent_task_id=None. Root task IDs should
    be UUIDs. Child task IDs follow the format T-{idx}.{subidx}... (e.g.,
    T-0, T-0.1, T-0.1.2) for efficient tree navigation via at_id().

    The _parent object reference (not a dataclass field — excluded from
    serialization) enables O(1) upward traversal. After deserialization,
    call set_parents() to re-establish parent references.

    Attributes:
        task_id: Unique identifier (UUID for root, T-{idx}... for children).
        parent_task_id: ID of the parent task (None for root).
        task_name: Short label for the task.
        task_description: Agent-readable prose describing what to do.
        task_context: Task-specific context in structured markdown.
        success_criteria: List of criteria for task completion.
        confidence: Agent-assigned confidence in decomposition or readiness.
        finished: Whether this task is complete. Leaf tasks can be
            finished/unfinished freely. Container tasks require all
            children finished before being marked finished.
        child_tasks: Optional list of child tasks. When present, this is
            a container task and is not executed directly.
    """

    task_id: str
    task_name: str
    task_description: str
    task_context: str
    success_criteria: list[str]
    confidence: float
    parent_task_id: str | None = None
    finished: bool = False
    child_tasks: list[Task] | None = None

    def __post_init__(self) -> None:
        """Validate finished constraint, sync parent_task_id, and set _parent."""
        # Initialize _parent (not a dataclass field — excluded from serialization)
        if not hasattr(self, "_parent"):
            object.__setattr__(self, "_parent", None)

        if self.child_tasks is not None:
            for child in self.child_tasks:
                # Set child's parent object reference
                object.__setattr__(child, "_parent", self)

                # Auto-set or validate parent_task_id
                if child.parent_task_id is None:
                    child.parent_task_id = self.task_id
                elif child.parent_task_id != self.task_id:
                    raise ValueError(
                        f"Child task '{child.task_id}' has parent_task_id "
                        f"'{child.parent_task_id}' but expected '{self.task_id}'"
                    )

            if self.finished and not all(c.finished for c in self.child_tasks):
                raise ValueError(
                    f"Cannot mark container task '{self.task_id}' as finished: "
                    "not all child tasks are finished"
                )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @property
    def parent(self) -> Task | None:
        """The parent task, or None if this is the root."""
        return self._parent  # type: ignore[attr-defined]

    def is_root(self) -> bool:
        """Check if this task is the root (no parent)."""
        return self._parent is None  # type: ignore[attr-defined]

    def root(self) -> Task:
        """Walk up the parent chain to return the root task."""
        current = self
        while current._parent is not None:  # type: ignore[attr-defined]
            current = current._parent  # type: ignore[attr-defined]
        return current

    def traverse(self) -> Task:
        """Find the next executable leaf task via DFS pre-order traversal.

        If this task is unfinished: descend to the deepest unfinished
        child in pre-order. Returns the first unfinished leaf.

        If this task is finished: walk up to the first unfinished
        ancestor, then traverse from there. If the root itself is
        finished, returns the root (meaning: all tasks done).

        Returns:
            The next leaf task to execute, or the finished root.
        """
        if self.finished:
            # Walk up to first unfinished ancestor
            current: Task = self
            while current._parent is not None and current.finished:  # type: ignore[attr-defined]
                current = current._parent  # type: ignore[attr-defined]
            if current.finished:
                # Root is finished — everything done
                return current
            return current.traverse()

        # This task is unfinished
        if self.child_tasks:
            for child in self.child_tasks:
                if not child.finished:
                    return child.traverse()
            # All children finished but self isn't — shouldn't happen
            # due to __post_init__ constraint, but handle gracefully
            return self
        # Leaf task, unfinished — ready to execute
        return self

    def at_id(self, task_id: str) -> Task:
        """Navigate to a task by its ID from anywhere in the tree.

        Navigates to the root first, then follows the index path encoded
        in the ID. Root IDs are opaque (e.g., UUID). Child IDs follow
        the format T-{idx}.{subidx}... corresponding to 0-based indices
        at each tree level.

        Args:
            task_id: The target task ID (root UUID or T-{idx}... format).

        Returns:
            The task with the matching ID.

        Raises:
            ValueError: If the ID format is unknown or the task is not
                found at the expected path.
        """
        r = self.root()
        if r.task_id == task_id:
            return r

        if not task_id.startswith("T-"):
            raise ValueError(
                f"Unknown task ID format: '{task_id}'. "
                "Expected root UUID or T-{idx}.{subidx}..."
            )

        indices_str = task_id[2:]  # strip "T-"
        indices = [int(i) for i in indices_str.split(".")]

        current = r
        for idx in indices:
            if current.child_tasks is None or idx >= len(current.child_tasks):
                raise ValueError(
                    f"No child at index {idx} for task '{current.task_id}' "
                    f"(ID '{task_id}' not found)"
                )
            current = current.child_tasks[idx]
            if current.task_id == task_id:
                return current

        raise ValueError(
            f"Task ID '{task_id}' not found at expected path"
        )

    def set_parents(self) -> None:
        """Walk the tree from this node and set _parent on all descendants.

        Must be called after deserialization (from_dict/from_json) to
        re-establish parent object references for navigation methods.
        This method is called automatically by Task.from_dict() and
        Task.from_json().
        """
        if self.child_tasks:
            for child in self.child_tasks:
                object.__setattr__(child, "_parent", self)
                child.set_parents()

    # ------------------------------------------------------------------
    # Serialization (override for parent refs)
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialize from dict, then re-establish parent references."""
        result = super().from_dict(data)
        result.set_parents()
        return result

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Deserialize from JSON, then re-establish parent references."""
        result = super().from_json(json_str)
        result.set_parents()
        return result

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display(self, indent: int = 0) -> str:
        """Return a DFS pre-order string representation of the full task tree.

        Always starts from the root, regardless of which node this is
        called on. Child tasks are indented by 2 spaces per level.

        Returns:
            A multi-line string of the entire tree, suitable for display.

        Example:
            [ ] - Research topic
              [ ] - Gather sources - T-0
                [x] - Read paper - T-0.0
              [ ] - Write summary - T-1
        """
        root = self.root()
        return root._display(indent=indent)

    def _display(self, indent: int = 0) -> str:
        """Internal: DFS pre-order display from this node (no root walk)."""
        marker = "x" if self.finished else " "
        prefix = "  " * indent
        if self.parent_task_id is None:
            line = f"{prefix}[{marker}] - {self.task_name}"
        else:
            line = f"{prefix}[{marker}] - {self.task_name} - {self.task_id}"

        lines = [line]
        if self.child_tasks:
            for child in self.child_tasks:
                lines.append(child._display(indent=indent + 1))
        return "\n".join(lines)
