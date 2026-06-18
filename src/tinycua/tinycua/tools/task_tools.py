"""Task mutation tools for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


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
    """Tool for updating task description, status, or metadata.

    Reviewers use this to curate context for unfinished tasks after approval.
    Completed tasks are immutable — updates to them are rejected.
    """

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_update",
            description=(
                "Update an existing task's description, status, or metadata. "
                "Use this to add context notes, mark planning state, or curate "
                "unfinished task descriptions with discoveries from completed work. "
                "Completed tasks cannot be updated — they are immutable history."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": (
                            "Task ID to update. Omit to update the active task."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "Updated task description. Use this to add relevant "
                            "context from completed work — file paths, discoveries, "
                            "or constraints that the next executor should know."
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
        description: str | None = None,
        status: str | None = None,
        **metadata: str,
    ) -> dict[str, Any]:
        """Update task description, status, and metadata."""
        active_id = task_id or self._store.active_task_id
        if active_id is None:
            return {"success": False, "error": "No active task"}
        try:
            task = self._store.get_task(active_id)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        if task.status == TaskStatus.COMPLETED:
            return {
                "success": False,
                "error": (
                    f"Task {active_id} is completed and immutable. "
                    "Completed tasks cannot be updated."
                ),
            }
        if status in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value}:
            return {
                "success": False,
                "error": (
                    "task_update only records planning or assessment metadata; "
                    "the requested status is not supported by this tool"
                ),
            }
        try:
            if status is not None:
                task = self._store.transition(active_id, TaskStatus(status))
            if description is not None:
                task.description = description
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
                "use a fixed template."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "subtasks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["task_id", "subtasks"],
                "additionalProperties": False,
            },
        )

    def __call__(self, task_id: str, subtasks: list[str]) -> dict[str, Any]:
        """Create child tasks below an existing task.

        Preserves every analyzer-provided subtask in order. TaskAnalyzer owns
        roadmap size; the runtime must not truncate, collapse, or rewrite it.
        Completed tasks cannot be decomposed — they are immutable history.
        """
        try:
            task = self._store.get_task(task_id)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        if task.status == TaskStatus.COMPLETED:
            return {
                "success": False,
                "error": (
                    f"Task {task_id} is completed and immutable. "
                    "Completed tasks cannot be decomposed."
                ),
            }
        try:
            child_ids = self._store.decompose_task(task_id, subtasks)
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
    """Tool for recording execution results on a task.

    The result content is a semantic report — a concise summary of what was
    done, what was found, and why the task succeeded or failed.  This report
    is the primary review target for the ResultReviewer; the reviewer verifies
    claims made in the report against tool-call evidence.  Every executor
    invocation MUST call this tool before finishing.
    """

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_result_update",
            description=(
                "Report the outcome for the active or specified task. "
                "Write a concise summary of what was done, what was found, "
                "and whether the task succeeded or failed. This report is "
                "the primary evidence the ResultReviewer will verify. "
                "Always call this tool before finishing — never leave a "
                "task without a result report."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "content": {
                        "type": "string",
                        "description": (
                            "Concise outcome report: what was done, what was "
                            "found, and why it succeeded or failed."
                        ),
                    },
                    "success": {"type": "boolean"},
                },
                "required": ["content", "success"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        task_id: str | None = None,
        content: str = "",
        success: bool = True,
    ) -> dict[str, Any]:
        """Persist a task execution result report."""
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
                "needs_revision, rejected, or replan."
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
