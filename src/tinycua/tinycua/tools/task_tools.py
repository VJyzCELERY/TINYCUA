"""Task mutation tool stubs for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

from tinycua.config.types import Tool


class TaskInitTool(Tool):
    """Tool stub for initializing a new task tree."""

    def __init__(self) -> None:
        super().__init__(name="task_init")


class TaskCreateTool(Tool):
    """Tool stub for creating child tasks under a parent."""

    def __init__(self) -> None:
        super().__init__(name="task_create")


class TaskInspectTool(Tool):
    """Tool stub for inspecting task state and hierarchy."""

    def __init__(self) -> None:
        super().__init__(name="task_inspect")


class TaskUpdateTool(Tool):
    """Tool stub for updating task status, fields, or metadata."""

    def __init__(self) -> None:
        super().__init__(name="task_update")


class TaskDecomposeTool(Tool):
    """Tool stub for decomposing a task into subtasks."""

    def __init__(self) -> None:
        super().__init__(name="task_decompose")


class TaskExecuteTool(Tool):
    """Tool stub for executing a task."""

    def __init__(self) -> None:
        super().__init__(name="task_execute")


class TaskResultUpdateTool(Tool):
    """Tool stub for recording execution results on a task."""

    def __init__(self) -> None:
        super().__init__(name="task_result_update")


class FinalResponseSynthesisTool(Tool):
    """Tool stub for synthesizing the final response."""

    def __init__(self) -> None:
        super().__init__(name="final_response_synthesis")
