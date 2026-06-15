"""Task mutation tool stubs for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

from tinycua.config.types import Tool
from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus


_DEFAULT_STORE = TaskStateStore()


class TaskInitTool(Tool):
    """Tool stub for initializing a new task tree."""

    def __init__(self) -> None:
        super().__init__(name="task_init")

    def __call__(self, title: str, description: str = "") -> dict[str, str]:
        """Initialize a root task tree."""
        _DEFAULT_STORE.tasks.clear()
        _DEFAULT_STORE.root_task_id = None
        task = _DEFAULT_STORE.create_task(title, description=description)
        return {"task_id": task.task_id, "status": task.status.value}


class TaskCreateTool(Tool):
    """Tool stub for creating child tasks under a parent."""

    def __init__(self) -> None:
        super().__init__(name="task_create")

    def __call__(
        self,
        title: str,
        parent_id: str | None = None,
        description: str = "",
    ) -> dict[str, str]:
        """Create a task in the in-memory task store."""
        task = _DEFAULT_STORE.create_task(
            title,
            parent_id=parent_id,
            description=description,
        )
        return {"task_id": task.task_id, "status": task.status.value}


class TaskInspectTool(Tool):
    """Tool stub for inspecting task state and hierarchy."""

    def __init__(self) -> None:
        super().__init__(name="task_inspect")

    def __call__(self) -> dict:
        """Return the current task tree state."""
        return {
            "root_task_id": _DEFAULT_STORE.root_task_id,
            "tasks": {task_id: task.__dict__ for task_id, task in _DEFAULT_STORE.tasks.items()},
        }


class TaskUpdateTool(Tool):
    """Tool stub for updating task status, fields, or metadata."""

    def __init__(self) -> None:
        super().__init__(name="task_update")

    def __call__(self, task_id: str, status: str | None = None, **metadata: str) -> dict:
        """Update task status and metadata."""
        task = _DEFAULT_STORE.tasks[task_id]
        if status is not None:
            task.status = TaskStatus(status)
        task.metadata.update(metadata)
        return {"task_id": task.task_id, "status": task.status.value}


class TaskDecomposeTool(Tool):
    """Tool stub for decomposing a task into subtasks."""

    def __init__(self) -> None:
        super().__init__(name="task_decompose")

    def __call__(self, task_id: str, subtasks: list[str]) -> dict[str, list[str]]:
        """Create child tasks below an existing task."""
        child_ids = [
            _DEFAULT_STORE.create_task(title, parent_id=task_id).task_id
            for title in subtasks
        ]
        return {"task_id": task_id, "child_task_ids": child_ids}


class TaskExecuteTool(Tool):
    """Tool stub for executing a task."""

    def __init__(self) -> None:
        super().__init__(name="task_execute")

    def __call__(self, task_id: str) -> dict[str, str]:
        """Mark a task as in progress for execution dispatch."""
        task = _DEFAULT_STORE.tasks[task_id]
        task.status = TaskStatus.IN_PROGRESS
        return {"task_id": task_id, "status": task.status.value}


class TaskResultUpdateTool(Tool):
    """Tool stub for recording execution results on a task."""

    def __init__(self) -> None:
        super().__init__(name="task_result_update")

    def __call__(self, task_id: str, content: str, success: bool = True) -> dict[str, str]:
        """Persist a task execution result."""
        task = _DEFAULT_STORE.tasks[task_id]
        task.result = TaskResult(content=content, success=success)
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        return {"task_id": task_id, "status": task.status.value}


class FinalResponseSynthesisTool(Tool):
    """Tool stub for synthesizing the final response."""

    def __init__(self) -> None:
        super().__init__(name="final_response_synthesis")

    def __call__(self) -> dict:
        """Return task state for final response synthesis."""
        return TaskInspectTool()()
