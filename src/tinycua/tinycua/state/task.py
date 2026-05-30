"""Task tree node state object with DFS navigation."""

from __future__ import annotations

__all__ = ["Task"]

import dataclasses
from typing import Any, Self

from tinycua.state.base import StateObject
from tinycua.state.task_result import TaskResult


@dataclasses.dataclass
class Task(StateObject):
    """A single node in the task execution tree.

    Tasks form a tree structure navigated via DFS pre-order traversal.
    A task with child_tasks is a container (not executed directly); a task
    with child_tasks=None is a leaf (executable).

    Each leaf task carries an optional TaskResult recording its execution
    outcome. task_result=None means not_started. Container task completion
    is derived from children: a container is completed when all its
    children are completed.

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
        task_result: Execution outcome (None = not_started). Only set on
            leaf tasks; containers derive status from children.
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
    task_result: TaskResult | None = None
    child_tasks: list[Task] | None = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _leaf_status(self) -> str | None:
        """Return the status string for a leaf task, or None if not_started."""
        if self.task_result is None:
            return None
        return self.task_result.status

    @property
    def is_completed(self) -> bool:
        """True if this task is done (leaf result = completed, or all children completed)."""
        if self.child_tasks is not None:
            return all(child.is_completed for child in self.child_tasks)
        return self.task_result is not None and self.task_result.status == "completed"

    def _status_marker(self) -> str:
        """Return the display marker character for this task's status.

        Leaf: derived from task_result status.
        Container: derived from children's aggregate status.
        """
        if self.child_tasks is not None:
            # Container: aggregate child statuses
            children = self.child_tasks
            if any(c._leaf_status() == "failed" for c in children):
                return "-"
            if any(c._leaf_status() == "blocked" for c in children):
                return "/"
            if any(c._leaf_status() == "inprogress" for c in children):
                return "*"
            if all(c.is_completed for c in children):
                return "x"
            return " "
        else:
            # Leaf
            if self.task_result is None:
                return " "
            mapping = {
                "inprogress": "*",
                "completed": "x",
                "failed": "-",
                "blocked": "/",
            }
            return mapping.get(self.task_result.status, " ")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Sync parent_task_id and set _parent on children."""
        if not hasattr(self, "_parent"):
            object.__setattr__(self, "_parent", None)

        if self.child_tasks is not None:
            for child in self.child_tasks:
                object.__setattr__(child, "_parent", self)

                if child.parent_task_id is None:
                    child.parent_task_id = self.task_id
                elif child.parent_task_id != self.task_id:
                    raise ValueError(
                        f"Child task '{child.task_id}' has parent_task_id "
                        f"'{child.parent_task_id}' but expected '{self.task_id}'"
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

        If this task is not completed: descend to the deepest
        non-completed child in pre-order. Returns the first
        non-completed leaf.

        If this task is completed: walk up to the first non-completed
        ancestor, then traverse from there. If the root itself is
        completed, returns the root (meaning: all tasks done).

        Returns:
            The next leaf task to execute, or the completed root.
        """
        if self.is_completed:
            # Walk up to first non-completed ancestor
            current: Task = self
            while current._parent is not None and current.is_completed:  # type: ignore[attr-defined]
                current = current._parent  # type: ignore[attr-defined]
            if current.is_completed:
                return current  # All done
            return current.traverse()

        # This task is not completed
        if self.child_tasks:
            for child in self.child_tasks:
                if not child.is_completed:
                    return child.traverse()
            return self
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

        indices_str = task_id[2:]
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
        """Walk the tree and set _parent on all descendants.

        Must be called after deserialization (from_dict/from_json) to
        re-establish parent object references. Called automatically by
        Task.from_dict() and Task.from_json().
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

    def display(self, indent: int = 0, trim: bool = False) -> str:
        """Return a DFS pre-order string representation of the task tree.

        By default, always starts from the root regardless of which node
        this is called on. Set trim=True to display only the subtree
        starting from this node.

        Markers:
            [ ] = not_started   [*] = inprogress   [x] = completed
            [-] = failed        [/] = blocked

        Args:
            indent: Initial indentation level in spaces (2 per level).
            trim: If True, show only the subtree from this node.

        Returns:
            A multi-line string suitable for display.
        """
        node = self if trim else self.root()
        return node._display(indent=indent)

    def _display(self, indent: int = 0) -> str:
        """Internal: DFS pre-order display from this node (no root walk)."""
        marker = self._status_marker()
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
