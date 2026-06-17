"""Task mutation tools for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


_DEFAULT_STORE = TaskStateStore()
_MAX_DECOMPOSE_SUBTASKS = 3
_ONE_SHOT_VERTICAL_SLICE_TITLE = (
    "Build a minimal runnable vertical-slice app with Python backend and web UI"
)


def _one_shot_app_subtasks(parent_title: str, subtasks: list[str]) -> list[str]:
    """Collapse app/web-ui splits into one runnable prototype task."""
    title = parent_title.lower()
    if len(subtasks) <= 1:
        return subtasks
    if "app" not in title or not ({"web", "ui"} & set(title.split())):
        return subtasks
    return [_ONE_SHOT_VERTICAL_SLICE_TITLE]


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
        Tool.__init__(
            self,
            name="task_init",
            description=(
                "Initialize the worker task tree with exactly one root task. "
                "Choose the title and description from the actual user request; "
                "do not create subtasks with this tool."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Concise root task title derived from the request.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional root task description/context.",
                    },
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        )

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
        Tool.__init__(
            self,
            name="task_create",
            description="Create one child task under an existing parent task.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "parent_id": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "parent_id"],
                "additionalProperties": False,
            },
        )

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
        Tool.__init__(
            self,
            name="task_inspect",
            description="Inspect the current task tree, active task, and statuses.",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )

    def __call__(self) -> dict[str, Any]:
        """Return the current task tree state."""
        return self._store.snapshot()


class TaskUpdateTool(SessionTaskToolMixin, Tool):
    """Tool for updating task status, fields, or metadata."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_update",
            description=(
                "Update an existing task status or metadata. Use this for "
                "assessment notes, selected decomposition targets, blocked state, "
                "or other explicit task metadata."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": (
                            "Optional task ID. Omit to update the active task."
                        ),
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "blocked"],
                        "description": (
                            "Planning/assessment status only for assessor/analyzer "
                            "metadata and decomposition readiness."
                        ),
                    },
                },
                "required": [],
                "additionalProperties": True,
            },
        )

    def __call__(
        self,
        task_id: str | None = None,
        status: str | None = None,
        **metadata: str,
    ) -> dict[str, Any]:
        """Update task status and metadata."""
        active_id = task_id or self._store.active_task_id
        if active_id is None:
            return {"success": False, "error": "No active task"}
        if status in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value}:
            return {
                "success": False,
                "error": (
                    "task_update only records planning or assessment metadata; "
                    "the requested status is not supported by this tool"
                ),
            }
        try:
            task = self._store.get_task(active_id)
            if status is not None:
                task = self._store.transition(active_id, TaskStatus(status))
            task.metadata.update(metadata)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": task.task_id, "status": task.status.value}


class TaskDecomposeTool(SessionTaskToolMixin, Tool):
    """Tool for decomposing a task into subtasks."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_decompose",
            description=(
                "Decompose an existing task into concrete sequential subtasks. "
                "Choose subtasks from the request and current task state; do not "
                "use a fixed template. For one-shot app builds, prefer one "
                "runnable vertical-slice subtask over separate backend/frontend/API tasks."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "subtasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": _MAX_DECOMPOSE_SUBTASKS,
                    },
                },
                "required": ["task_id", "subtasks"],
                "additionalProperties": False,
            },
        )

    def __call__(self, task_id: str, subtasks: list[str]) -> dict[str, Any]:
        """Create child tasks below an existing task."""
        try:
            # ponytail: prototype one-shot cap; add scheduler batching if larger trees matter.
            task = self._store.get_task(task_id)
            selected_subtasks = _one_shot_app_subtasks(task.title, subtasks)
            child_ids = self._store.decompose_task(
                task_id,
                selected_subtasks[:_MAX_DECOMPOSE_SUBTASKS],
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "task_id": task_id, "child_task_ids": child_ids}


class TaskExecuteTool(SessionTaskToolMixin, Tool):
    """Tool for marking a task as actively executing."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_execute",
            description="Mark the active or specified task as actively executing.",
            parameters={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "additionalProperties": False,
            },
        )

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
        Tool.__init__(
            self,
            name="task_result_update",
            description=(
                "Record the execution result for the active or specified task "
                "after observing action/research/tool evidence."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "content": {"type": "string"},
                    "success": {"type": "boolean"},
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        )

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


class TaskReviewDecisionTool(SessionTaskToolMixin, Tool):
    """Tool for recording reviewer decisions on task results."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_review_decision",
            description=(
                "Record the review decision for a task result: approved, "
                "needs_revision, rejected, replan, or open_question."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": [
                            "approved",
                            "needs_revision",
                            "rejected",
                            "replan",
                            "open_question",
                        ],
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["decision"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        task_id: str | None = None,
        decision: str = ReviewerDecision.APPROVED.value,
        rationale: str = "",
    ) -> dict[str, Any]:
        """Persist a reviewer decision for the active or specified task."""
        active_id = task_id or self._store.active_task_id
        if active_id is None:
            for task in reversed(list(self._store.tasks.values())):
                if task.result is not None and not task.reviewer_decisions:
                    active_id = task.task_id
                    break
        if active_id is None:
            return {"success": False, "error": "No active task"}
        try:
            task = self._store.record_reviewer_decision(
                active_id,
                ReviewerDecision(decision),
                rationale=rationale,
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {
            "success": True,
            "task_id": active_id,
            "decision": ReviewerDecision(decision).value,
            "status": task.status.value,
        }


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
