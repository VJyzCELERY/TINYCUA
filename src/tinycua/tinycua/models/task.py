"""Task state models for TinyCUA worker execution."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


def _normalized_task_title(title: str) -> str:
    """Return a title key for deterministic sibling de-duplication."""
    return " ".join(title.casefold().split())


class TaskStatus(StrEnum):
    """Lifecycle status for a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ReviewerDecision(StrEnum):
    """Review decision for a task result.

    ``OPEN_QUESTION`` is disabled by default (``enable_open_question_review``
    in :class:`SessionConfig`). When enabled, the reviewer may bail to the
    ResponseNode for unresolved upstream questions; when disabled (default),
    the reviewer must not bail while tasks remain unfinished.
    """

    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"
    REPLAN = "replan"
    OPEN_QUESTION = "open_question"


@dataclass
class TaskResult:
    """Persisted result for a task execution."""

    content: str
    task_id: str | None = None
    execution_status: str = "succeeded"
    reviewer_decision: str | None = None
    summary: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Keep legacy content and design summary fields aligned."""
        if not self.summary:
            self.summary = self.content


@dataclass
class WorkerResult:
    """Aggregated worker-mode result."""

    summary: str
    task_results: list[TaskResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedResult:
    """Response-ready aggregation of a completed worker task tree."""

    root_task_id: str
    task_summaries: list[str] = field(default_factory=list)
    accepted_results: list[TaskResult] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    final_context: str = ""
    response_continuation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Session-local task tree node."""

    title: str
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    description: str = ""
    children: list[str] = field(default_factory=list)
    active_child_id: str | None = None
    result: TaskResult | None = None
    reviewer_decisions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failure_count(self) -> int:
        """Number of times review has sent this task back (needs_revision/rejected/replan).

        Derived from the ``reviewer_decisions`` audit trail — no separate
        counter to keep in sync. Used by the reviewer continuation as soft
        context so the reviewer can weigh replan vs retry itself (FR-021).
        """
        back_decisions = {
            ReviewerDecision.NEEDS_REVISION.value,
            ReviewerDecision.REJECTED.value,
            ReviewerDecision.REPLAN.value,
        }
        return sum(
            1
            for d in self.reviewer_decisions
            if d.get("decision") in back_decisions
        )

    @property
    def consecutive_failures(self) -> int:
        """Count of consecutive needs_revision/rejected/replan decisions.

        Counts backward from the latest reviewer decision until an ``approved``
        OR a ``replan_boundary`` entry is hit. The boundary marker is inserted
        by ``schedule_replan`` (FR-049) so the failure baseline resets when a
        replan is triggered, without losing the audit trail. This is the
        deterministic replan trigger: when this count reaches
        ``replan_threshold`` (default 5), the runtime routes to TaskAnalyzer
        for replan instead of retrying the executor.
        """
        back_decisions = {
            ReviewerDecision.NEEDS_REVISION.value,
            ReviewerDecision.REJECTED.value,
            ReviewerDecision.REPLAN.value,
        }
        count = 0
        for d in reversed(self.reviewer_decisions):
            decision = d.get("decision")
            if decision in back_decisions:
                count += 1
            else:
                break  # approved or replan_boundary — breaks the consecutive run
        return count


@dataclass
class TaskStateStore:
    """Session-owned task tree with active-task traversal and transitions."""

    tasks: dict[str, Task] = field(default_factory=dict)
    root_task_id: str | None = None
    active_task_id: str | None = None
    transition_log: list[dict[str, Any]] = field(default_factory=list)
    _staged_reviewer_decisions: dict[str, dict[str, Any]] = field(
        default_factory=dict, repr=False
    )
    _staged_results: dict[str, TaskResult] = field(default_factory=dict, repr=False)
    # FR-075: enable task tree snapshot logging via --trace CLI flag.
    _enable_trace: bool = field(default=False, repr=False)
    # Internal flag to suppress per-child logging during decompose_task.
    _suppress_log: bool = field(default=False, repr=False)
    # ponytail: cached post-order task id list (root excluded) for O(1)
    # number lookup. None = stale; rebuilt lazily on next access. Invalidated
    # only on structural change (create_task) — status transitions don't
    # reorder the tree. Upgrade path: per-subtree incremental rebuild if huge
    # trees with frequent decomposition ever make the full rebuild costly.
    _ordered_task_ids: list[str] | None = field(default=None, repr=False)
    # Monotonic version — bumped on EVERY mutation (structural or status). Used
    # as the cache key for _render_task_tree_markdown so it only re-renders when
    # the tree actually changed, keeping continuation bytes stable for prompt
    # caching. Starts at 0; first read of any render is a cache miss by design.
    version: int = 0

    _ALLOWED_TRANSITIONS: ClassVar[dict[TaskStatus, set[TaskStatus]]] = {
        TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
        TaskStatus.IN_PROGRESS: {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.PENDING,
        },
        TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.FAILED},
        TaskStatus.FAILED: {TaskStatus.PENDING, TaskStatus.IN_PROGRESS},
        TaskStatus.COMPLETED: set(),
        TaskStatus.CANCELLED: set(),
        TaskStatus.SUPERSEDED: set(),
    }
    _TERMINAL_STATUSES: ClassVar[set[TaskStatus]] = {
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
        TaskStatus.SUPERSEDED,
    }

    def _bump_version(self) -> None:
        """Increment the monotonic version (called on every mutation)."""
        self.version += 1

    def validate_tree(self) -> None:  # noqa: C901
        """Validate the retained task tree before committing a mutation."""
        if self.root_task_id is None:
            if self.tasks:
                msg = "Task tree has tasks but no root."
                raise ValueError(msg)
            return
        if self.root_task_id not in self.tasks:
            msg = f"Root task not found: {self.root_task_id}"
            raise ValueError(msg)
        root = self.tasks[self.root_task_id]
        if root.parent_id is not None:
            msg = "Root task cannot have a parent."
            raise ValueError(msg)

        visited: set[str] = set()

        def visit(task_id: str, ancestors: set[str]) -> None:
            if task_id in ancestors:
                msg = f"Task tree contains a cycle at {task_id}."
                raise ValueError(msg)
            if task_id in visited:
                msg = f"Task {task_id} is reachable more than once."
                raise ValueError(msg)
            task = self.tasks.get(task_id)
            if task is None:
                msg = f"Task link references missing task: {task_id}"
                raise ValueError(msg)
            if len(task.children) != len(set(task.children)):
                msg = f"Task {task_id} has duplicate child links."
                raise ValueError(msg)
            visited.add(task_id)
            for child_id in task.children:
                child = self.tasks.get(child_id)
                if child is None:
                    msg = f"Task link references missing task: {child_id}"
                    raise ValueError(msg)
                if child.parent_id != task_id:
                    msg = f"Task {child_id} does not agree with parent {task_id}."
                    raise ValueError(msg)
                visit(child_id, ancestors | {task_id})

        visit(self.root_task_id, set())
        if visited != set(self.tasks):
            msg = "Task tree contains unreachable tasks."
            raise ValueError(msg)
        for task_id, task in self.tasks.items():
            if task_id == self.root_task_id:
                continue
            if task.parent_id not in self.tasks:
                msg = f"Task {task_id} has a missing parent."
                raise ValueError(msg)
            if self.tasks[task.parent_id].children.count(task_id) != 1:
                msg = f"Task {task_id} does not have exactly one parent link."
                raise ValueError(msg)

    def _finalize_mutation(
        self, action: str, task_id: str | None = None, **event: Any
    ) -> None:
        """Publish one validated mutation to readers, caches, and the audit trail."""
        self.validate_tree()
        self._ordered_task_ids = None
        self._render_cache = None
        self.transition_log.append({"action": action, "task_id": task_id, **event})
        self._bump_version()
        self._refresh_active_task()
        self._log_tree_snapshot(action)

    def _require_mutable(self, task: Task) -> None:
        """Reject mutations of terminal task history."""
        if task.status in self._TERMINAL_STATUSES:
            msg = f"Task {task.task_id} is {task.status.value} and immutable."
            raise ValueError(msg)

    def _log_tree_snapshot(self, method: str) -> None:
        """Log the task tree state after a mutation (FR-075).

        Multi-line INFO: header (method + counts + active/root) then one
        line per task (numbered, status, title, has_result marker). Only
        fires when ``_enable_trace`` is True (set via ``--trace`` CLI flag).
        """
        if not self._enable_trace:
            return
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        in_progress = sum(1 for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS)
        active = self.active_task_id or "none"
        root = self.root_task_id or "none"
        lines = [
            f"task_tree_mutation method={method} root={root} active={active} "
            f"completed={completed}/{total} pending={pending} in_progress={in_progress}"
        ]
        ordered = self._ordered_ids()
        for i, task_id in enumerate(ordered, 1):
            task = self.tasks.get(task_id)
            if task is None:
                continue
            marker = " ✓" if task.result is not None else ""
            lines.append(f"  {i}. [{task.status.value}] {task.title}{marker}")
        logger.info("\n".join(lines))

    def create_task(
        self,
        title: str,
        *,
        parent_id: str | None = None,
        description: str = "",
        acceptance_clauses: list[str] | None = None,
        clause_ids: list[str] | None = None,
    ) -> Task:
        """Create and store a task."""
        self.validate_tree()
        if parent_id is not None and parent_id not in self.tasks:
            msg = f"Parent task not found: {parent_id}"
            raise ValueError(msg)
        if parent_id is not None:
            self._require_mutable(self.tasks[parent_id])
        if self.root_task_id is not None and parent_id is None:
            msg = "New tasks require an existing parent."
            raise ValueError(msg)
        if acceptance_clauses is not None and parent_id is not None:
            msg = "Only the root task can define acceptance clauses."
            raise ValueError(msg)
        metadata: dict[str, Any] = {}
        if acceptance_clauses:
            metadata["acceptance_clauses"] = [
                {"id": f"acceptance-{index}", "text": text}
                for index, text in enumerate(acceptance_clauses, start=1)
                if text.strip()
            ]
        if clause_ids:
            root = self.tasks.get(self.root_task_id or "")
            valid_ids = {
                clause["id"]
                for clause in (root.metadata.get("acceptance_clauses", []) if root else [])
                if isinstance(clause, dict) and isinstance(clause.get("id"), str)
            }
            if not set(clause_ids).issubset(valid_ids):
                msg = "Task references an unknown acceptance clause."
                raise ValueError(msg)
            metadata["acceptance_clause_ids"] = list(dict.fromkeys(clause_ids))
        if parent_id is not None and any(
            _normalized_task_title(self.tasks[child_id].title)
            == _normalized_task_title(title)
            for child_id in self.tasks[parent_id].children
        ):
            msg = "Task duplicates an existing sibling title."
            raise ValueError(msg)
        task = Task(
            title=title,
            parent_id=parent_id,
            description=description,
            metadata=metadata,
        )
        self.tasks[task.task_id] = task
        if parent_id:
            self.tasks[parent_id].children.append(task.task_id)
        if self.root_task_id is None:
            self.root_task_id = task.task_id
        self._finalize_mutation("create_task", task.task_id)
        return task

    def decompose_task(self, task_id: str, subtasks: list[Any]) -> list[str]:
        """Append child tasks below an unfinished parent."""
        task = self.get_task(task_id)
        self.validate_tree()
        self._require_mutable(task)
        definitions = [
            item if isinstance(item, dict) else {"title": item}
            for item in subtasks
            if isinstance(item, dict) or (isinstance(item, str) and item.strip())
        ]
        if not definitions:
            return list(task.children)
        root = self.tasks[self.root_task_id] if self.root_task_id else task
        required_ids = {
            clause["id"]
            for clause in root.metadata.get("acceptance_clauses", [])
            if isinstance(clause, dict) and isinstance(clause.get("id"), str)
        }
        supplied_ids = {
            clause_id
            for definition in definitions
            for clause_id in definition.get("clause_ids", [])
            if isinstance(clause_id, str)
        }
        if not supplied_ids.issubset(required_ids):
            msg = "Task references an unknown acceptance clause."
            raise ValueError(msg)
        sibling_titles = {
            _normalized_task_title(self.tasks[child_id].title)
            for child_id in task.children
        }
        titled_definitions: list[tuple[dict[str, Any], str]] = []
        for definition in definitions:
            title = str(definition.get("title", "")).strip()
            if not title:
                continue
            title_key = _normalized_task_title(title)
            if title_key in sibling_titles:
                msg = "Task duplicates an existing sibling title."
                raise ValueError(msg)
            sibling_titles.add(title_key)
            titled_definitions.append((definition, title))
        for definition, title in titled_definitions:
            child = Task(
                title=title,
                parent_id=task_id,
                metadata={
                    "acceptance_clause_ids": list(
                        dict.fromkeys(definition.get("clause_ids", []))
                    )
                }
                if definition.get("clause_ids")
                else {},
            )
            self.tasks[child.task_id] = child
            task.children.append(child.task_id)
        self._finalize_mutation("decompose_task", task_id, child_count=len(definitions))
        return list(task.children)

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Apply validated content edits through the authoritative store."""
        self.validate_tree()
        task = self.get_task(task_id)
        self._require_mutable(task)
        if title is None and description is None and status is None and not metadata:
            msg = "Task update requires at least one change."
            raise ValueError(msg)
        next_status = TaskStatus(status) if status is not None else task.status
        if next_status in {TaskStatus.CANCELLED, TaskStatus.SUPERSEDED}:
            msg = "Use cancellation or supersession with a rationale."
            raise ValueError(msg)
        if next_status != task.status and next_status not in self._ALLOWED_TRANSITIONS[task.status]:
            msg = f"Invalid task transition {task.status.value}->{next_status.value} for task {task_id}"
            raise ValueError(msg)
        if metadata and "acceptance_clause_ids" in metadata:
            self._require_acceptance_coverage(
                task_id, metadata["acceptance_clause_ids"]
            )
        if metadata and task_id == self.root_task_id and "acceptance_clauses" in metadata:
            msg = "Root acceptance clauses are immutable."
            raise ValueError(msg)
        task.title = title if title is not None else task.title
        task.description = description if description is not None else task.description
        task.status = next_status
        if metadata:
            task.metadata.update(metadata)
        self._finalize_mutation("update_task", task_id)
        return task

    def cancel_task(self, task_id: str, rationale: str) -> Task:
        """Retain an impossible unfinished task as terminal history."""
        self.validate_tree()
        task = self.get_task(task_id)
        if task_id == self.root_task_id:
            msg = "Cannot cancel the root task."
            raise ValueError(msg)
        self._require_mutable(task)
        if not rationale.strip():
            msg = "Cancellation requires a rationale."
            raise ValueError(msg)
        self._require_acceptance_coverage(task_id, [])
        task.status = TaskStatus.CANCELLED
        task.metadata["cancellation_rationale"] = rationale
        self._finalize_mutation("cancel_task", task_id, rationale=rationale)
        return task

    def supersede_task(
        self, task_id: str, replacement_title: str, rationale: str, description: str = ""
    ) -> Task:
        """Replace unfinished work while retaining bidirectional lineage."""
        self.validate_tree()
        task = self.get_task(task_id)
        if task_id == self.root_task_id:
            msg = "Cannot supersede the root task."
            raise ValueError(msg)
        self._require_mutable(task)
        if not rationale.strip() or not replacement_title.strip():
            msg = "Supersession requires a rationale and replacement title."
            raise ValueError(msg)
        parent = self.tasks[task.parent_id] if task.parent_id else None
        if parent is None:
            msg = f"Task {task_id} has no parent."
            raise ValueError(msg)
        self._require_mutable(parent)
        clause_ids = list(task.metadata.get("acceptance_clause_ids", []))
        replacement = Task(
            title=replacement_title,
            parent_id=parent.task_id,
            description=description,
            metadata={
                "supersedes": task_id,
                "supersession_rationale": rationale,
                **({"acceptance_clause_ids": clause_ids} if clause_ids else {}),
            },
        )
        task.status = TaskStatus.SUPERSEDED
        task.metadata["superseded_by"] = replacement.task_id
        task.metadata["supersession_rationale"] = rationale
        self.tasks[replacement.task_id] = replacement
        parent.children.insert(parent.children.index(task_id) + 1, replacement.task_id)
        self._finalize_mutation(
            "supersede_task", task_id, replacement_task_id=replacement.task_id, rationale=rationale
        )
        return replacement

    def delete_task(self, task_id: str, *, rationale: str) -> None:
        """Delete an untouched unfinished planning leaf, including the active leaf."""
        self.validate_tree()
        task = self.get_task(task_id)
        if task_id == self.root_task_id:
            msg = "Cannot delete the root task."
            raise ValueError(msg)
        if not rationale.strip():
            msg = "Deletion requires a rationale."
            raise ValueError(msg)
        self._require_mutable(task)
        if task.status != TaskStatus.PENDING or task.result or task.reviewer_decisions or task.artifacts:
            msg = f"Task {task_id} is not an untouched unfinished task."
            raise ValueError(msg)
        if task.children:
            msg = "Cannot delete a task with descendants."
            raise ValueError(msg)
        parent = self.tasks[task.parent_id] if task.parent_id else None
        if parent is None:
            msg = f"Task {task_id} has no parent."
            raise ValueError(msg)
        self._require_mutable(parent)
        self._require_acceptance_coverage(task_id, [])
        parent.children.remove(task_id)
        del self.tasks[task_id]
        self._finalize_mutation("delete_task", task_id, rationale=rationale)

    def _require_acceptance_coverage(self, task_id: str, clause_ids: Any) -> None:
        """Reject a mutation that leaves a root acceptance clause unowned."""
        if not isinstance(clause_ids, list) or not all(
            isinstance(clause_id, str) for clause_id in clause_ids
        ):
            msg = "Acceptance clause references must be a list of clause IDs."
            raise ValueError(msg)
        root = self.tasks.get(self.root_task_id or "")
        required_ids = {
            clause["id"]
            for clause in (root.metadata.get("acceptance_clauses", []) if root else [])
            if isinstance(clause, dict) and isinstance(clause.get("id"), str)
        }
        if not set(clause_ids).issubset(required_ids):
            msg = "Task references an unknown acceptance clause."
            raise ValueError(msg)
        covered_ids = {
            clause_id
            for candidate_id, candidate in self.tasks.items()
            if candidate.status not in {TaskStatus.CANCELLED, TaskStatus.SUPERSEDED}
            for clause_id in (
                clause_ids
                if candidate_id == task_id
                else candidate.metadata.get("acceptance_clause_ids", [])
            )
            if isinstance(clause_id, str)
        }
        if not required_ids.issubset(covered_ids):
            msg = "Cannot remove the final owner of an acceptance clause."
            raise ValueError(msg)

    def merge_tasks(self, child_id: str, parent_id: str, *, rationale: str) -> Task:
        """Collapse a child into its parent, preserving work.

        If the child has a result and the parent does not, the child's result
        becomes the parent's result (preserve work). If both have results, the
        child's summary is appended to the parent's. The child's pending subtree
        is discarded. The child is removed from the parent's children list.

        Args:
            child_id: The child task to merge into its parent.
            parent_id: The parent task.
            rationale: Why the merge is needed for the audit trail.

        Returns:
            The updated parent task.

        Raises:
            ValueError: If child == parent, either is completed, or not found.
        """
        self.validate_tree()
        if child_id == parent_id:
            msg = "Cannot merge a task into itself."
            raise ValueError(msg)
        if child_id not in self.tasks or parent_id not in self.tasks:
            msg = f"Task not found: {child_id if child_id not in self.tasks else parent_id}"
            raise ValueError(msg)
        child = self.tasks[child_id]
        parent = self.tasks[parent_id]
        if child.parent_id != parent_id:
            msg = "Merge target must be the task's direct parent."
            raise ValueError(msg)
        if not rationale.strip():
            msg = "Merge requires a rationale."
            raise ValueError(msg)
        if child.status in self._TERMINAL_STATUSES or parent.status in self._TERMINAL_STATUSES:
            msg = "Cannot merge — one or both tasks are completed (immutable)."
            raise ValueError(msg)
        if any(
            self.tasks[child_id].status not in self._TERMINAL_STATUSES
            for child_id in child.children
        ):
            msg = "Cannot merge a task with unfinished descendants."
            raise ValueError(msg)
        # Preserve work: child's result → parent's result if parent has none.
        if child.result is not None:
            if parent.result is None:
                parent.result = child.result
            elif child.result.summary:
                parent.result.summary = (
                    f"{parent.result.summary}\n\nMerged from {child.title}: "
                    f"{child.result.summary}"
                )
        clause_ids = [
            *parent.metadata.get("acceptance_clause_ids", []),
            *child.metadata.get("acceptance_clause_ids", []),
        ]
        if clause_ids:
            parent.metadata["acceptance_clause_ids"] = list(dict.fromkeys(clause_ids))
        child_index = parent.children.index(child_id)
        parent.children[child_index : child_index + 1] = child.children
        for grandchild_id in child.children:
            self.tasks[grandchild_id].parent_id = parent_id
        self.tasks.pop(child_id, None)
        self._finalize_mutation("merge_tasks", child_id, parent_id=parent_id, rationale=rationale)
        return parent

    def get_task(self, task_id: str) -> Task:
        """Return a task or raise a clear validation error."""
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            msg = f"Task not found: {task_id}"
            raise ValueError(msg) from exc

    def get_active_task(self) -> Task | None:
        """Return the active leaf task, refreshing traversal if needed."""
        if self.active_task_id not in self.tasks:
            self._refresh_active_task()
        if self.active_task_id is None:
            return None
        return self.tasks[self.active_task_id]

    def _ordered_ids(self) -> list[str]:
        """Return the cached post-order task id list (root excluded), 1-based.

        Built once per structural change (create_task invalidates the cache)
        and reused across lookups/render. Post-order DFS so index 1 is the
        left-most leaf (first executed); root is excluded (it is the goal).
        """
        if self._ordered_task_ids is not None:
            return self._ordered_task_ids
        ordered: list[str] = []
        if self.root_task_id is not None and self.root_task_id in self.tasks:

            def visit(task_id: str) -> None:
                task = self.tasks[task_id]
                for child_id in task.children:
                    if child_id in self.tasks:
                        visit(child_id)
                if task_id != self.root_task_id:
                    ordered.append(task_id)

            visit(self.root_task_id)
        self._ordered_task_ids = ordered
        return ordered

    def task_number_map(self) -> dict[int, str]:
        """Return a 1-based number -> task_id map in execution order.

        Post-order DFS over the tree, root excluded: the first entry is the
        left-most leaf (the first task executed), the last is the right-most
        node. This numbering matches the rendered roadmap so an agent can refer
        to a task by its number instead of a hallucination-prone UUID.
        """
        ordered = self._ordered_ids()
        return {index: task_id for index, task_id in enumerate(ordered, start=1)}

    def resolve_task_id(self, task_id: str | None) -> str | None:
        """Resolve a task reference to a concrete task_id.

        Accepts either a task UUID (existing behaviour) or a task number string
        matching the rendered roadmap's 1-based post-order numbering. Returns
        the active task id when ``task_id`` is None/empty. Returns None if the
        reference does not resolve.
        """
        if not task_id:
            return self.active_task_id
        if task_id in self.tasks:
            return task_id
        # Try numeric reference (1-based post-order index, root excluded).
        try:
            number = int(task_id)
        except (TypeError, ValueError):
            return None
        ordered = self._ordered_ids()
        if 1 <= number <= len(ordered):
            return ordered[number - 1]
        return None

    def transition(self, task_id: str, status: TaskStatus | str) -> Task:
        """Transition a task after validating its lifecycle edge."""
        self.validate_tree()
        task = self.get_task(task_id)
        self._require_mutable(task)
        next_status = TaskStatus(status)
        allowed = self._ALLOWED_TRANSITIONS[task.status]
        if next_status != task.status and next_status not in allowed:
            msg = (
                "Invalid task transition "
                f"{task.status.value}->{next_status.value} for task {task_id}"
            )
            raise ValueError(msg)
        previous = task.status
        task.status = next_status
        self._finalize_mutation(
            "transition", task_id, **{"from": previous.value, "to": next_status.value}
        )
        return task

    def record_result(self, task_id: str, result: TaskResult) -> Task:
        """Persist task execution output without completing review state."""
        task = self.get_task(task_id)
        self._require_mutable(task)
        if task.status in {TaskStatus.PENDING, TaskStatus.FAILED}:
            self.transition(task_id, TaskStatus.IN_PROGRESS)
        task.result = result
        self._finalize_mutation("record_result", task_id)
        return task

    def stage_result(self, task_id: str, result: TaskResult) -> Task:
        """Stage a task result until the executor terminates."""
        task = self.get_task(task_id)
        self._require_mutable(task)
        self._staged_results.pop(task_id, None)
        self._staged_results[task_id] = result
        return task

    def commit_staged_result(self, task_id: str) -> Task:
        """Commit the executor's staged result exactly once at termination."""
        result = self._staged_results.pop(task_id, None)
        if result is None:
            msg = "No provisional task result is staged."
            raise ValueError(msg)
        return self.record_result(task_id, result)

    @staticmethod
    def _has_approval_evidence(result: TaskResult | None) -> bool:
        """Return whether an executor result can support approval."""
        return bool(
            result
            and result.success
            and result.content.strip()
            and not result.metadata.get("auto_generated")
        )

    def _has_current_clause_evidence(self, task: Task) -> bool:
        """Return whether every clause owned by task has passing evidence."""
        clause_ids = task.metadata.get("acceptance_clause_ids", [])
        if not clause_ids:
            return True
        evidence = task.result.metadata.get("clause_evidence", {}) if task.result else {}
        return all(
            isinstance(evidence.get(clause_id), list)
            and any(
                isinstance(item, dict) and item.get("passed") is True
                for item in evidence[clause_id]
            )
            for clause_id in clause_ids
        )

    def _root_has_current_clause_evidence(self) -> bool:
        """Return whether every explicit root clause has passing accepted evidence."""
        if self.root_task_id is None:
            return True
        root = self.tasks[self.root_task_id]
        clause_ids = [
            clause["id"]
            for clause in root.metadata.get("acceptance_clauses", [])
            if isinstance(clause, dict) and isinstance(clause.get("id"), str)
        ]
        for clause_id in clause_ids:
            if not any(
                task.status == TaskStatus.COMPLETED
                and task.result is not None
                and any(
                    item.get("passed") is True
                    for item in task.result.metadata.get("clause_evidence", {}).get(clause_id, [])
                )
                for task in self.tasks.values()
            ):
                return False
        return True

    def unmet_acceptance_clauses(self, task: Task | None = None) -> list[dict[str, str]]:
        """Return root clauses without current passing evidence."""
        if self.root_task_id is None:
            return []
        root = self.tasks[self.root_task_id]
        clauses = [
            clause
            for clause in root.metadata.get("acceptance_clauses", [])
            if isinstance(clause, dict)
            and isinstance(clause.get("id"), str)
            and isinstance(clause.get("text"), str)
        ]
        if task is not None:
            owned = set(task.metadata.get("acceptance_clause_ids", []))
            clauses = [clause for clause in clauses if clause["id"] in owned]
        return [
            clause
            for clause in clauses
            if not any(
                completed.status == TaskStatus.COMPLETED
                and completed.result is not None
                and any(
                    evidence.get("passed") is True
                    for evidence in completed.result.metadata.get("clause_evidence", {}).get(
                        clause["id"], []
                    )
                )
                for completed in self.tasks.values()
            )
        ]

    def record_reviewer_decision(
        self,
        task_id: str,
        decision: ReviewerDecision | str,
        *,
        rationale: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Append a reviewer decision to a task audit trail."""
        task = self.get_task(task_id)
        self._require_mutable(task)
        reviewer_decision = ReviewerDecision(decision)
        if (
            reviewer_decision == ReviewerDecision.APPROVED
            and not self._has_approval_evidence(task.result)
        ):
            if task.status == TaskStatus.PENDING:
                self.transition(task_id, TaskStatus.IN_PROGRESS)
            msg = "Approval requires successful executor evidence with non-empty content."
            raise ValueError(msg)
        if reviewer_decision == ReviewerDecision.APPROVED and not self._has_current_clause_evidence(task):
            msg = "Approval requires current passing evidence for every acceptance clause."
            raise ValueError(msg)
        if (
            reviewer_decision == ReviewerDecision.APPROVED
            and task_id == self.root_task_id
            and not self._root_has_current_clause_evidence()
        ):
            msg = "Root approval requires current passing evidence for every acceptance clause."
            raise ValueError(msg)
        task.reviewer_decisions.append(
            {
                "decision": reviewer_decision.value,
                "rationale": rationale,
                "metadata": metadata or {},
            }
        )
        if reviewer_decision in {
            ReviewerDecision.NEEDS_REVISION,
            ReviewerDecision.REJECTED,
            ReviewerDecision.REPLAN,
        }:
            if task.status != TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.IN_PROGRESS
            self.active_task_id = task.task_id
            self._bump_version()
        elif reviewer_decision == ReviewerDecision.APPROVED:
            if task.status == TaskStatus.PENDING:
                self.transition(task_id, TaskStatus.IN_PROGRESS)
            self.transition(task_id, TaskStatus.COMPLETED)
            self._complete_ready_parents()
            self._propagate_result_to_next_sibling(task)
            self._refresh_active_task()
            self._bump_version()
        self._finalize_mutation("record_reviewer_decision", task_id)
        return task

    def stage_reviewer_decision(
        self,
        task_id: str,
        decision: ReviewerDecision | str,
        *,
        rationale: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Stage a replaceable reviewer decision until node termination."""
        task = self.get_task(task_id)
        self._require_mutable(task)
        reviewer_decision = ReviewerDecision(decision)
        if reviewer_decision == ReviewerDecision.APPROVED and not self._has_approval_evidence(task.result):
            msg = "Approval requires successful executor evidence with non-empty content."
            raise ValueError(msg)
        self._staged_reviewer_decisions.pop(task_id, None)
        self._staged_reviewer_decisions[task_id] = {
            "decision": reviewer_decision,
            "rationale": rationale,
            "metadata": metadata,
        }
        return task

    def commit_staged_reviewer_decision(self, task_id: str) -> Task:
        """Commit exactly the latest provisional reviewer decision."""
        staged = self._staged_reviewer_decisions.get(task_id)
        if staged is None:
            msg = "No provisional reviewer decision is staged."
            raise ValueError(msg)
        task = self.record_reviewer_decision(task_id, **staged)
        del self._staged_reviewer_decisions[task_id]
        return task

    def next_unfinished_leaf(self) -> Task | None:
        """Return the first leaf that still needs work.

        Failed tasks are intentionally unfinished in one-shot worker runs. A
        failed reviewed result means the same task must be retried or locally
        replanned/decomposed; it is not a terminal state that permits sibling
        advancement or final aggregation.
        """
        if self.root_task_id is None:
            return None

        def visit(task_id: str) -> Task | None:
            task = self.tasks[task_id]
            if task.children:
                for child_id in task.children:
                    found = visit(child_id)
                    if found is not None:
                        return found
                if task.status not in self._TERMINAL_STATUSES:
                    return task
                return None
            if task.status not in self._TERMINAL_STATUSES:
                return task
            return None

        return visit(self.root_task_id)

    def all_done(self) -> bool:
        """Return True when no retained task remains executable."""
        return bool(self.tasks) and all(
            task.status in self._TERMINAL_STATUSES for task in self.tasks.values()
        )

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe task tree snapshot."""
        return {
            "root_task_id": self.root_task_id,
            "active_task_id": self.active_task_id,
            "tasks": {
                task_id: self._json_safe(asdict(task))
                for task_id, task in self.tasks.items()
            },
            "transition_log": list(self.transition_log),
        }

    def snapshot_compact(self) -> dict[str, Any]:
        """Return a compact task LIST for quick scanning (FR-011).

        No descriptions, results, reviewer_decisions, artifacts, metadata, or
        transition_log — just ``{id, title, status, has_result}`` per task.
        This is what ``task_inspect`` with no ``task_id`` returns so the
        reviewer can scan the roadmap cheaply before drilling into a specific
        task for detail.
        """
        return {
            "root_task_id": self.root_task_id,
            "active_task_id": self.active_task_id,
            "tasks": [
                {
                    "id": task_id,
                    "title": task.title,
                    "status": task.status.value,
                    "has_result": task.result is not None,
                }
                for task_id, task in self.tasks.items()
            ],
        }

    def compact_task_detail(self, task_id: str) -> dict[str, Any] | None:
        """Return one task with compacted detail (FR-012), or None if not found.

        - ``reviewer_decisions`` truncated to the last 2.
        - ``result.content``/``result.summary`` truncated to 200 chars.
        - Empty ``metadata``/``artifacts``/``children`` omitted.
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None
        detail: dict[str, Any] = {
            "id": task.task_id,
            "title": task.title,
            "status": task.status.value,
            "parent_id": task.parent_id,
            "description": task.description,
        }
        if task.children:
            detail["children"] = list(task.children)
        if task.active_child_id:
            detail["active_child_id"] = task.active_child_id
        if task.result is not None:
            result = task.result
            detail["result"] = {
                "success": result.success,
                "content": result.content[:200],
                "summary": result.summary[:200],
            }
            if result.artifacts:
                detail["result"]["artifacts"] = result.artifacts
        if task.reviewer_decisions:
            detail["reviewer_decisions"] = list(task.reviewer_decisions[-2:])
        if task.artifacts:
            detail["artifacts"] = task.artifacts
        if task.metadata:
            detail["metadata"] = task.metadata
        return self._json_safe(detail)

    def _refresh_active_task(self) -> None:
        """Refresh active_task_id to the first unfinished leaf."""
        active = self.next_unfinished_leaf()
        self.active_task_id = active.task_id if active is not None else None
        for task in self.tasks.values():
            task.active_child_id = None
        if active is None:
            return
        current = active
        while current.parent_id is not None and current.parent_id in self.tasks:
            parent = self.tasks[current.parent_id]
            parent.active_child_id = current.task_id
            current = parent

    def _complete_ready_parents(self) -> None:
        """Auto-transition parent tasks to IN_PROGRESS when all children complete.

        Parent tasks (root, phases) are NOT auto-completed here — they need
        a real verification pass by the TaskExecutor (does all the child work
        actually achieve the parent's goal?). The executor calls
        task_result_update with the verification result, then the reviewer
        reviews it, and THEN the parent completes via record_reviewer_decision.

        This method only transitions PENDING parents to IN_PROGRESS so they
        become the active task and get scheduled for execution.
        """
        for task in self.tasks.values():
            if not task.children or task.status in self._TERMINAL_STATUSES:
                continue
            children = [self.tasks[child_id] for child_id in task.children]
            if all(
                child.status in {TaskStatus.CANCELLED, TaskStatus.SUPERSEDED}
                or (
                    child.status == TaskStatus.COMPLETED
                    and self._has_approval_evidence(child.result)
                )
                for child in children
            ):
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.IN_PROGRESS
                    self._bump_version()

    def _propagate_result_to_next_sibling(self, task: Task) -> None:
        """Propagate an approved task's result summary to the next pending sibling.

        When a task is approved, its result summary is appended to the
        ``metadata["context"]`` of the next pending sibling under the same
        parent. This ensures the downstream task sees the approved result
        in its "Useful Prior Context" section (Milestone 8 Stream A).
        """
        if task.parent_id is None or task.parent_id not in self.tasks:
            return
        if not self._has_approval_evidence(task.result):
            return
        parent = self.tasks[task.parent_id]
        # Find the next pending sibling (in children order, after this task).
        found_self = False
        for child_id in parent.children:
            if child_id == task.task_id:
                found_self = True
                continue
            if not found_self:
                continue
            child = self.tasks.get(child_id)
            if child and child.status == TaskStatus.PENDING:
                summary = task.result.summary or task.result.content
                existing = child.metadata.setdefault("context", "")
                if existing:
                    child.metadata["context"] = (
                        f"{existing}\n\n[From completed sibling '{task.title}']: "
                        f"{summary}"
                    )
                else:
                    child.metadata["context"] = (
                        f"[From completed sibling '{task.title}']: {summary}"
                    )
                break

    def _json_safe(self, value: Any) -> Any:
        """Convert dataclass fields to JSON-compatible primitives."""
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, dict):
            return {key: self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value

    # ponytail: cached markdown render of the task tree, keyed on version.
    # Re-renders only when the tree mutates (version bumps). Keeps the
    # continuation bytes stable across calls that don't change task state
    # (helps prompt-cache prefix stability). Upgrade path: invalidate on
    # selective subtree changes if partial renders ever matter.
    _render_cache: tuple[int, str] = field(default=None, repr=False)

    def render_markdown(self) -> str:
        """Return a cached markdown render of the task tree (FR-014).

        Mirrors ``_render_task_tree_markdown(_task_context_snapshot(session))``
        but caches the result keyed on ``version`` so repeated calls in a node's
        retry loop don't re-render or change the continuation bytes.
        """
        if self._render_cache is not None and self._render_cache[0] == self.version:
            return self._render_cache[1]
        from tinycua.loops.task_nodes import _render_task_tree_markdown, _task_context_snapshot_from_store

        text = _render_task_tree_markdown(_task_context_snapshot_from_store(self))
        # Avoid a hard import cycle at module load: build the snapshot lazily.
        self._render_cache = (self.version, text)
        return text
