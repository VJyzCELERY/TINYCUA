"""Task mutation tool stubs for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

from tinycua.config.types import Tool
from dataclasses import asdict

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
    """Tool stub for initializing a new task tree."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_init")

    def __call__(self, title: str, description: str = "") -> dict[str, str]:
        """Initialize a root task tree."""
        self._store.tasks.clear()
        self._store.root_task_id = None
        task = self._store.create_task(title, description=description)
        return {"task_id": task.task_id, "status": task.status.value}


class TaskCreateTool(SessionTaskToolMixin, Tool):
    """Tool stub for creating child tasks under a parent."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_create")

    def __call__(
        self,
        title: str,
        parent_id: str | None = None,
        description: str = "",
    ) -> dict[str, str]:
        """Create a task in the in-memory task store."""
        task = self._store.create_task(
            title,
            parent_id=parent_id,
            description=description,
        )
        return {"task_id": task.task_id, "status": task.status.value}


class TaskInspectTool(SessionTaskToolMixin, Tool):
    """Tool stub for inspecting task state and hierarchy."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_inspect")

    def __call__(self) -> dict:
        """Return the current task tree state."""
        return {
            "root_task_id": self._store.root_task_id,
            "tasks": {task_id: asdict(task) for task_id, task in self._store.tasks.items()},
        }


class TaskUpdateTool(SessionTaskToolMixin, Tool):
    """Tool stub for updating task status, fields, or metadata."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_update")

    def __call__(self, task_id: str, status: str | None = None, **metadata: str) -> dict:
        """Update task status and metadata."""
        task = self._store.tasks[task_id]
        if status is not None:
            task.status = TaskStatus(status)
        task.metadata.update(metadata)
        return {"task_id": task.task_id, "status": task.status.value}


class TaskDecomposeTool(SessionTaskToolMixin, Tool):
    """Tool stub for decomposing a task into subtasks."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_decompose")

    def __call__(self, task_id: str, subtasks: list[str]) -> dict[str, list[str]]:
        """Create child tasks below an existing task."""
        child_ids = [
            self._store.create_task(title, parent_id=task_id).task_id
            for title in subtasks
        ]
        return {"task_id": task_id, "child_task_ids": child_ids}


class TaskExecuteTool(SessionTaskToolMixin, Tool):
    """Tool stub for executing a task."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_execute")

    def __call__(self, task_id: str) -> dict[str, str]:
        """Mark a task as in progress for execution dispatch."""
        task = self._store.tasks[task_id]
        task.status = TaskStatus.IN_PROGRESS
        return {"task_id": task_id, "status": task.status.value}


class TaskResultUpdateTool(SessionTaskToolMixin, Tool):
    """Tool stub for recording execution results on a task."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="task_result_update")

    def __call__(self, task_id: str, content: str, success: bool = True) -> dict[str, str]:
        """Persist a task execution result."""
        task = self._store.tasks[task_id]
        task.result = TaskResult(content=content, success=success)
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        return {"task_id": task_id, "status": task.status.value}


class FinalResponseSynthesisTool(SessionTaskToolMixin, Tool):
    """Tool stub for synthesizing the final response."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(self, name="final_response_synthesis")

    def __call__(self) -> dict:
        """Return task state for final response synthesis."""
        tool = TaskInspectTool()
        tool.bind_task_store(self._store)
        return tool()
