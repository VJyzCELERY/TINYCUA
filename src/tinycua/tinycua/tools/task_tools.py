"""Task mutation tools for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool
from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus


_DEFAULT_STORE = TaskStateStore()


class SessionTaskToolMixin:
    """Mixin for tools that can bind to a session-owned task store."""

    def __init__(self) -> None:
        self._store = _DEFAULT_STORE

    def bind_task_store(self, store: TaskStateStore) -> None:
        """Bind this tool instance to the active session's task store."""
        self._store = store


class TaskInitTool(SessionTaskToolMixin, Tool):
    """Tool for initializing a new task tree."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_init")

    def __call__(self, title: str, description: str = "") -> dict[str, Any]:
        """Initialize a root task tree."""
        self._store.tasks.clear()
        self._store.root_task_id = None
        self._store.active_task_id = None
        self._store.transition_log.clear()
        task = self._store.create_task(title, description=description)
        return {"success": True, "task_id": task.task_id, "status": task.status.value}


class TaskCreateTool(SessionTaskToolMixin, Tool):
    """Tool for creating child tasks under a parent."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_create")

    def __call__(
        self,
        title: str,
        parent_id: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a task in the in-memory task store."""
        try:
            task = self._store.create_task(
                title,
                parent_id=parent_id,
                description=description,
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": task.task_id, "status": task.status.value}


class TaskInspectTool(SessionTaskToolMixin, Tool):
    """Tool for inspecting task state and hierarchy."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_inspect")

    def __call__(self) -> dict[str, Any]:
        """Return the current task tree state."""
        return self._store.snapshot()


class TaskUpdateTool(SessionTaskToolMixin, Tool):
    """Tool for updating task status, fields, or metadata."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_update")

    def __call__(self, task_id: str, status: str | None = None, **metadata: str) -> dict[str, Any]:
        """Update task status and metadata."""
        try:
            task = self._store.get_task(task_id)
            if status is not None:
                task = self._store.transition(task_id, TaskStatus(status))
            task.metadata.update(metadata)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": task.task_id, "status": task.status.value}


class TaskDecomposeTool(SessionTaskToolMixin, Tool):
    """Tool for decomposing a task into subtasks."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_decompose")

    def __call__(self, task_id: str, subtasks: list[str]) -> dict[str, Any]:
        """Create child tasks below an existing task."""
        try:
            child_ids = [
                self._store.create_task(title, parent_id=task_id).task_id
                for title in subtasks
                if title.strip()
            ]
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": task_id, "child_task_ids": child_ids}


class TaskExecuteTool(SessionTaskToolMixin, Tool):
    """Tool for marking a task as actively executing."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_execute")

    def __call__(self, task_id: str | None = None) -> dict[str, Any]:
        """Mark a task as in progress for execution dispatch."""
        active_id = task_id or self._store.active_task_id
        if active_id is None:
            return {"success": False, "error": "No active task"}
        try:
            task = self._store.transition(active_id, TaskStatus.IN_PROGRESS)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": active_id, "status": task.status.value}


class TaskResultUpdateTool(SessionTaskToolMixin, Tool):
    """Tool for recording execution results on a task."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_result_update")

    def __call__(
        self,
        task_id: str | None = None,
        content: str = "",
        success: bool = True,
    ) -> dict[str, Any]:
        """Persist a task execution result."""
        active_id = task_id or self._store.active_task_id
        if active_id is None:
            return {"success": False, "error": "No active task"}
        try:
            task = self._store.record_result(
                active_id,
                TaskResult(content=content, success=success),
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": active_id, "status": task.status.value}


class FinalResponseSynthesisTool(SessionTaskToolMixin, Tool):
    """Tool for exposing task state to final response synthesis."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="final_response_synthesis")

    def __call__(self) -> dict:
        """Return task state for final response synthesis."""
        tool = TaskInspectTool()
        tool.bind_task_store(self._store)
        return tool()
