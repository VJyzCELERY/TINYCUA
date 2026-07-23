"""Task mutation tools for TinyCUA nodes.

Provides concrete Tool instances for task lifecycle operations:
TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate.
"""

from __future__ import annotations

import logging
from typing import Any

from tinycua.config.types import Tool
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus

logger = logging.getLogger(__name__)


_DEFAULT_STORE = TaskStateStore()


class TerminateTool(Tool):
    """Tool for explicitly ending a worker lifecycle node."""

    def __init__(self) -> None:
        self._store = _DEFAULT_STORE
        self._source_node = ""
        Tool.__init__(
            self,
            name="terminate",
            description="End the current node after its required work is complete.",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )

    def bind_task_store(self, store: TaskStateStore) -> None:
        """Bind termination to the active session's task store."""
        self._store = store

    def bind_source_node(self, node_id: str) -> None:
        """Bind the terminating lifecycle node."""
        self._source_node = node_id

    def __call__(self) -> dict[str, Any]:
        """Record an explicit node termination request."""
        result: dict[str, Any] = {"success": True, "terminated": True}
        if self._source_node == "result_reviewer":
            if not self._store._staged_reviewer_decisions:
                return {"success": False, "error": "No provisional reviewer decision is staged."}
            try:
                task = self._store.commit_staged_reviewer_decision(
                    next(reversed(self._store._staged_reviewer_decisions))
                )
            except ValueError as exc:
                return {"success": False, "error": str(exc)}
            result["task_id"] = task.task_id
            result["decision"] = task.reviewer_decisions[-1]["decision"]
        if self._source_node == "task_executor":
            if self._store._staged_results:
                try:
                    task = self._store.commit_staged_result(
                        next(reversed(self._store._staged_results))
                    )
                except ValueError as exc:
                    return {"success": False, "error": str(exc)}
                result["task_id"] = task.task_id
        return result


class SessionTaskToolMixin:
    """Mixin for tools that can bind to a session-owned task store."""

    def __init__(self) -> None:
        self._store = _DEFAULT_STORE

    def bind_task_store(self, store: TaskStateStore) -> None:
        """Bind this tool instance to the active session's task store."""
        self._store = store

    def _resolve_task_ref(
        self, task_id: str | None
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Resolve a task_id (UUID or number) to a concrete task_id.

        Returns ``(resolved_id, None)`` on success, or ``(None, error_dict)``
        when the reference is unresolvable. Distinguishes a bad explicit
        reference (echoes it in the error) from an omitted one with no active
        task.
        """
        if task_id:
            resolved = self._store.resolve_task_id(task_id)
            if resolved is None:
                return None, {"success": False, "error": f"Task {task_id} not found."}
            return resolved, None
        active = self._store.active_task_id
        if active is None:
            return None, {"success": False, "error": "No active task"}
        return active, None


class TaskInitTool(SessionTaskToolMixin, Tool):
    """Tool for initializing a new task tree."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_init",
            description=(
                "Initialize the worker roadmap with exactly one root task. "
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
                    "acceptance_clauses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Explicit observable user acceptance clauses.",
                    },
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        title: str,
        description: str = "",
        acceptance_clauses: list[str] | None = None,
    ) -> dict[str, Any]:
        """Initialize a root task tree."""
        self._store.tasks.clear()
        self._store.root_task_id = None
        self._store.active_task_id = None
        self._store.transition_log.clear()
        task = self._store.create_task(
            title,
            description=description,
            acceptance_clauses=acceptance_clauses,
        )
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
    """Tool for inspecting task state and hierarchy.

    Two-tier (FR-011/FR-012):
    - No ``task_id`` → returns a compact list ``[{id, title, status, has_result}]``
      for the whole tree. Cheap to render and to put in the prompt; this is the
      "scan the roadmap" mode.
    - With ``task_id`` → returns one task with compacted detail (last 2
      reviewer_decisions, result truncated to 200 chars, empty fields dropped).
      This is the "drill into a specific task" mode.
    ``task_id`` may be a UUID or the task's 1-based number from the rendered
    roadmap.
    """

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_inspect",
            description=(
                "Inspect task state. Without task_id, returns a compact list "
                "of all tasks (id, title, status, has_result) — scan this "
                "first. With task_id, returns compacted detail for one task "
                "(last 2 reviewer decisions, result truncated to 200 chars). "
                "task_id may be a UUID or the task's 1-based number from the "
                "rendered roadmap."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": (
                            "Specific task ID to inspect for detail. Omit to "
                            "get the compact list of all tasks."
                        ),
                    },
                },
                "additionalProperties": False,
            },
        )

    def __call__(self, *, task_id: str | None = None) -> dict[str, Any]:
        """Return the compact list (no task_id) or compacted detail (with task_id)."""
        if task_id is not None:
            resolved = self._store.resolve_task_id(task_id)
            if resolved is None or resolved not in self._store.tasks:
                return {"error": f"Task {task_id} not found."}
            detail = self._store.compact_task_detail(resolved)
            return detail if detail is not None else {"error": f"Task {task_id} not found."}
        return self._store.snapshot_compact()


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
                "Update an unfinished task's description, status, or metadata; "
                "use for planning notes or context from completed work. Completed "
                "tasks are immutable. task_id may be UUID or roadmap number."
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
                    "title": {
                        "type": "string",
                        "description": (
                            "Updated task title. Use to correct a stale or "
                            "mistaken title from task_init; the new title "
                            "propagates to all downstream roadmap renderings."
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
                "additionalProperties": {"type": "string"},
            },
        )

    def __call__(
        self,
        task_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        **metadata: str,
    ) -> dict[str, Any]:
        """Update task title, description, status, and metadata."""
        active_id, error = self._resolve_task_ref(task_id)
        if error is not None:
            return error
        if status in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value}:
            return {
                "success": False,
                "error": (
                    "task_update only records planning or assessment metadata; "
                    "the requested status is not supported by this tool"
                ),
            }
        try:
            task = self._store.update_task(
                active_id,
                title=title,
                description=description,
                status=status,
                metadata=metadata,
            )
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
                "Choose subtasks from the request and current state; do not use a "
                "fixed template. task_id may be UUID or roadmap number."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "subtasks": {
                        "type": "array",
                        "items": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "clause_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                    "required": ["title"],
                                    "additionalProperties": False,
                                },
                            ]
                        },
                    },
                },
                "required": ["task_id", "subtasks"],
                "additionalProperties": False,
            },
        )

    def __call__(self, task_id: str, subtasks: list[Any]) -> dict[str, Any]:
        """Create child tasks below an existing task.

        Preserves every analyzer-provided subtask in order. TaskAnalyzer owns
        roadmap size; the runtime must not truncate, collapse, or rewrite it.
        Completed tasks cannot be decomposed — they are immutable history.
        """
        resolved = self._store.resolve_task_id(task_id)
        if resolved is None:
            return {"success": False, "error": f"Task {task_id} not found."}
        try:
            task = self._store.get_task(resolved)
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
            child_ids = self._store.decompose_task(resolved, subtasks)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        # FR-002: propagate inherited constraints from parent to each new child.
        parent_constraints = task.metadata.get("inherited_constraints", [])
        if parent_constraints:
            for child_id in child_ids:
                child = self._store.tasks.get(child_id)
                if child is None:
                    continue
                # Only set when absent — never overwrite a child's own constraints.
                if not child.metadata.get("inherited_constraints"):
                    child.metadata["inherited_constraints"] = list(parent_constraints)
        return {"success": True, "task_id": resolved, "child_task_ids": child_ids}


class TaskShrinkTool(SessionTaskToolMixin, Tool):
    """Tool for shrinking the task tree (delete or merge) to correct over-decomposition."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_shrink",
            description=(
                "Repair the task tree by deleting an untouched planning leaf, "
                "merging a child into its direct parent, cancelling impossible "
                "work, or superseding it with a replacement. "
                "task_id may be UUID or roadmap number."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["delete", "merge", "cancel", "supersede"],
                    },
                    "task_id": {"type": "string"},
                    "parent_id": {"type": "string"},
                    "rationale": {"type": "string"},
                    "replacement_title": {"type": "string"},
                    "replacement_description": {"type": "string"},
                },
                "required": ["action", "task_id", "rationale"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        action: str,
        task_id: str,
        rationale: str,
        parent_id: str | None = None,
        replacement_title: str | None = None,
        replacement_description: str = "",
    ) -> dict[str, Any]:
        """Delete or merge a task to shrink the tree.

        Args:
            action: "delete" or "merge".
            task_id: The task to delete or the child to merge.
            rationale: Why this shrink is needed (for audit trail).
            parent_id: Required for merge — the parent to merge into.
            replacement_title: Required when superseding a task.
            replacement_description: Optional context for the replacement task.
        """
        resolved = self._store.resolve_task_id(task_id)
        if resolved is None:
            return {"success": False, "error": f"Task {task_id} not found."}
        if not rationale.strip():
            return {"success": False, "error": "rationale is required."}
        try:
            if action == "delete":
                self._store.delete_task(resolved, rationale=rationale)
                logger.info("task_tree_shrink action=delete task_id=%s rationale=%s new_tree_size=%d",
                            resolved, rationale[:100], len(self._store.tasks))
                return {"success": True, "action": "delete", "task_id": resolved, "rationale": rationale}
            if action == "merge":
                if parent_id is None:
                    return {"success": False, "error": "parent_id is required for merge."}
                resolved_parent = self._store.resolve_task_id(parent_id)
                if resolved_parent is None:
                    return {"success": False, "error": f"Parent {parent_id} not found."}
                self._store.merge_tasks(resolved, resolved_parent, rationale=rationale)
                logger.info("task_tree_shrink action=merge task_id=%s parent_id=%s rationale=%s new_tree_size=%d",
                            resolved, resolved_parent, rationale[:100], len(self._store.tasks))
                return {"success": True, "action": "merge", "task_id": resolved, "parent_id": resolved_parent, "rationale": rationale}
            if action == "cancel":
                task = self._store.cancel_task(resolved, rationale)
                return {"success": True, "action": "cancel", "task_id": resolved, "status": task.status.value}
            if action == "supersede":
                replacement = self._store.supersede_task(
                    resolved, replacement_title or "", rationale, replacement_description
                )
                return {
                    "success": True,
                    "action": "supersede",
                    "task_id": resolved,
                    "replacement_task_id": replacement.task_id,
                    "status": TaskStatus.SUPERSEDED.value,
                }
            return {"success": False, "error": f"Unknown action: {action}."}
        except ValueError as exc:
            return {"success": False, "error": str(exc)}


class TaskExecuteTool(SessionTaskToolMixin, Tool):
    """Tool for marking a task as actively executing."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_execute",
            description="Mark the active or specified task as actively executing. "
            "task_id may be a UUID or the task's 1-based number from the roadmap.",
            parameters={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "additionalProperties": False,
            },
        )

    def __call__(self, task_id: str | None = None) -> dict[str, Any]:
        """Mark a task as in progress for execution dispatch."""
        active_id, error = self._resolve_task_ref(task_id)
        if error is not None:
            return error
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
        self._source_node = ""
        Tool.__init__(
            self,
            name="task_result_update",
            description=(
                "Report the outcome for the active or specified task. "
                "Set success=true when done, success=false when failed or "
                "blocked. Always call before finishing. task_id may be UUID "
                "or roadmap number."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "content": {
                        "type": "string",
                        "description": (
                            "Concise outcome report: what was done, what "
                            "was found, and why it succeeded or failed. "
                            "Set success=true for completed work, "
                            "success=false for failed/blocked work."
                        ),
                    },
                    "success": {"type": "boolean"},
                    "metadata": {
                        "type": "object",
                        "description": "Clause evidence, call identities, outcomes, and artifacts.",
                    },
                },
                "required": ["content", "success"],
                "additionalProperties": False,
            },
        )

    def bind_source_node(self, node_id: str) -> None:
        """Bind the node so executor results can be staged."""
        self._source_node = node_id

    def __call__(
        self,
        task_id: str | None = None,
        content: str = "",
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a task execution result report."""
        active_id, error = self._resolve_task_ref(task_id)
        if error is not None:
            return error
        try:
            result = TaskResult(content=content, success=success, metadata=metadata or {})
            if self._source_node == "task_executor":
                task = self._store.stage_result(active_id, result)
                staged = True
            else:
                task = self._store.record_result(active_id, result)
                staged = False
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        return {
            "success": True,
            "task_id": active_id,
            "status": task.status.value,
            "staged": staged,
        }


class TaskReviewDecisionTool(SessionTaskToolMixin, Tool):
    """Tool for recording reviewer decisions on task results."""

    def __init__(self) -> None:
        SessionTaskToolMixin.__init__(self)
        Tool.__init__(
            self,
            name="task_review_decision",
            description=(
                "Record the review decision for a task result: approved, "
                "needs_revision, rejected, or replan. task_id may be a UUID or "
                "roadmap number. needs_revision and rejected are aliases — "
                "use needs_revision for clarity."
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
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Required validation evidence. For approved: "
                            "'[validated]: <command+result confirming the "
                            "outcome>'. For needs_revision/rejected/replan: "
                            "'[finding]: <issue> [validate]: <command to "
                            "verify the fix>'."
                        ),
                    },
                },
                "required": ["decision", "rationale"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        task_id: str | None = None,
        decision: str = "",
        rationale: str = "",
    ) -> dict[str, Any]:
        """Persist a reviewer decision for the active or specified task.

        Args:
            task_id: Optional task reference (UUID or roadmap number).
            decision: Required — one of approved, needs_revision, rejected,
                replan. Must not be omitted (no default approve).
            rationale: Optional reason for the decision.
        """
        if not decision:
            return {"success": False, "error": "decision is required — cannot default to approved."}
        active_id: str | None
        if task_id:
            active_id = self._store.active_task_id if task_id == "active" else self._store.resolve_task_id(task_id)
            if active_id is None:
                return {"success": False, "error": f"Task {task_id} not found."}
        else:
            active_id = self._store.active_task_id
            if active_id is None:
                for task in reversed(list(self._store.tasks.values())):
                    if task.result is not None and not task.reviewer_decisions:
                        active_id = task.task_id
                        break
        if active_id is None:
            return {"success": False, "error": "No active task"}
        try:
            task = self._store.stage_reviewer_decision(
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
            "staged": True,
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
