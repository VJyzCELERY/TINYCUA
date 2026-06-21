"""Task state models for TinyCUA worker execution."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, ClassVar


class TaskStatus(StrEnum):
    """Lifecycle status for a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


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
        """Count of consecutive needs_revision/rejected/replan decisions (resets on approve).

        Counts backward from the latest reviewer decision until an ``approved``
        is hit. This is the deterministic replan trigger: when this count
        reaches ``replan_threshold`` (default 5), the runtime routes to
        TaskAnalyzer for replan instead of retrying the executor.
        """
        back_decisions = {
            ReviewerDecision.NEEDS_REVISION.value,
            ReviewerDecision.REJECTED.value,
            ReviewerDecision.REPLAN.value,
        }
        count = 0
        for d in reversed(self.reviewer_decisions):
            if d.get("decision") in back_decisions:
                count += 1
            else:
                break  # approved — breaks the consecutive run
        return count


@dataclass
class TaskStateStore:
    """Session-owned task tree with active-task traversal and transitions."""

    tasks: dict[str, Task] = field(default_factory=dict)
    root_task_id: str | None = None
    active_task_id: str | None = None
    transition_log: list[dict[str, Any]] = field(default_factory=list)
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
    }

    def _bump_version(self) -> None:
        """Increment the monotonic version (called on every mutation)."""
        self.version += 1

    def create_task(
        self,
        title: str,
        *,
        parent_id: str | None = None,
        description: str = "",
    ) -> Task:
        """Create and store a task."""
        if parent_id is not None and parent_id not in self.tasks:
            msg = f"Parent task not found: {parent_id}"
            raise ValueError(msg)
        task = Task(title=title, parent_id=parent_id, description=description)
        self.tasks[task.task_id] = task
        if parent_id:
            self.tasks[parent_id].children.append(task.task_id)
        if self.root_task_id is None:
            self.root_task_id = task.task_id
        self._ordered_task_ids = None  # structural change: invalidate cache
        self._bump_version()
        self._refresh_active_task()
        return task

    def decompose_task(self, task_id: str, subtasks: list[str]) -> list[str]:
        """Create child tasks only for an undecomposed parent.

        Decomposition is intentionally idempotent. Once a parent owns children,
        repeated analyzer/replan passes must refine metadata or focus on a local
        child, not append another copy of the same roadmap.
        """
        task = self.get_task(task_id)
        if task.children:
            return list(task.children)
        child_ids = []
        for title in subtasks:
            if title.strip():
                child_ids.append(self.create_task(title, parent_id=task_id).task_id)
        return child_ids

    def delete_task(self, task_id: str) -> None:
        """Remove a task and its pending subtree, re-linking siblings.

        Completed tasks are immutable history and cannot be deleted. The root
        task and the active task cannot be deleted (runtime integrity). Only
        pending or in-progress tasks (and their pending subtrees) can be
        removed — this lets the TaskAnalyzer correct over-decomposition mid-run.

        Args:
            task_id: The task to delete.

        Raises:
            ValueError: If the task is completed, not found, is the root, or
                is the active task.
        """
        if task_id not in self.tasks:
            msg = f"Task not found: {task_id}"
            raise ValueError(msg)
        task = self.tasks[task_id]
        if task.status == TaskStatus.COMPLETED:
            msg = f"Task {task_id} is completed and immutable."
            raise ValueError(msg)
        if task_id == self.root_task_id:
            msg = "Cannot delete the root task."
            raise ValueError(msg)
        if task_id == self.active_task_id:
            msg = "Cannot delete the active task."
            raise ValueError(msg)
        # Remove from parent's children list.
        if task.parent_id and task.parent_id in self.tasks:
            parent = self.tasks[task.parent_id]
            parent.children = [c for c in parent.children if c != task_id]
        # Recursively delete the subtree (only pending/in-progress — skip
        # completed children, they're immutable history).
        to_remove: list[str] = []

        def collect(tid: str) -> None:
            t = self.tasks.get(tid)
            if t is None:
                return
            for child_id in list(t.children):
                child = self.tasks.get(child_id)
                if child and child.status != TaskStatus.COMPLETED:
                    collect(child_id)
                elif child_id in self.tasks:
                    # Completed child stays — re-parent to the deleted task's parent.
                    if task.parent_id and task.parent_id in self.tasks:
                        self.tasks[task.parent_id].children.append(child_id)
                        child.parent_id = task.parent_id
            to_remove.append(tid)

        collect(task_id)
        for tid in to_remove:
            self.tasks.pop(tid, None)
        self._ordered_task_ids = None
        self._bump_version()
        self._refresh_active_task()

    def merge_tasks(self, child_id: str, parent_id: str) -> Task:
        """Collapse a child into its parent, preserving work.

        If the child has a result and the parent does not, the child's result
        becomes the parent's result (preserve work). If both have results, the
        child's summary is appended to the parent's. The child's pending subtree
        is discarded. The child is removed from the parent's children list.

        Args:
            child_id: The child task to merge into its parent.
            parent_id: The parent task.

        Returns:
            The updated parent task.

        Raises:
            ValueError: If child == parent, either is completed, or not found.
        """
        if child_id == parent_id:
            msg = "Cannot merge a task into itself."
            raise ValueError(msg)
        if child_id not in self.tasks or parent_id not in self.tasks:
            msg = f"Task not found: {child_id if child_id not in self.tasks else parent_id}"
            raise ValueError(msg)
        child = self.tasks[child_id]
        parent = self.tasks[parent_id]
        if child.status == TaskStatus.COMPLETED or parent.status == TaskStatus.COMPLETED:
            msg = "Cannot merge — one or both tasks are completed (immutable)."
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
        # Move child's completed children to parent (preserve immutable history).
        for cc_id in list(child.children):
            cc = self.tasks.get(cc_id)
            if cc is not None and cc.status == TaskStatus.COMPLETED:
                parent.children.append(cc_id)
                cc.parent_id = parent_id
            elif cc is not None:
                # Pending child — discard (the merge collapses the subtree).
                pass
        # Remove child from parent's children.
        parent.children = [c for c in parent.children if c != child_id]
        # Delete the child (and its pending subtree).
        self.tasks.pop(child_id, None)
        self._ordered_task_ids = None
        self._bump_version()
        self._refresh_active_task()
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
        task = self.get_task(task_id)
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
        self.transition_log.append(
            {
                "task_id": task_id,
                "from": previous.value,
                "to": next_status.value,
            }
        )
        self._bump_version()
        self._refresh_active_task()
        return task

    def record_result(self, task_id: str, result: TaskResult) -> Task:
        """Persist task execution output without completing review state."""
        task = self.get_task(task_id)
        if task.status in {TaskStatus.PENDING, TaskStatus.FAILED}:
            self.transition(task_id, TaskStatus.IN_PROGRESS)
        task.result = result
        self._bump_version()
        self._refresh_active_task()
        return task

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
        reviewer_decision = ReviewerDecision(decision)
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
            # Fallback for parent tasks: the executor runs a verification pass
            # on parent tasks (post-order traversal — all children done first).
            # If the executor forgot to call task_result_update, auto-generate
            # a synthetic "all children completed" result so the approval can
            # proceed instead of crashing. The executor gets its chance first
            # (via the Verification Pass continuation); this is the safety net.
            if task.result is None and task.children:
                all_children_done = all(
                    self.tasks[cid].status == TaskStatus.COMPLETED
                    for cid in task.children
                    if cid in self.tasks
                )
                if all_children_done:
                    task.result = TaskResult(
                        content="All child tasks completed — parent goal achieved.",
                        success=True,
                        metadata={"aggregated": True},
                    )
            if task.result is not None:
                target = TaskStatus.COMPLETED if task.result.success else TaskStatus.FAILED
                if task.status != target:
                    # Parent tasks may be IN_PROGRESS (from _complete_ready_parents)
                    # or PENDING. IN_PROGRESS→COMPLETED is allowed; PENDING is not.
                    if task.status == TaskStatus.PENDING:
                        task.status = TaskStatus.IN_PROGRESS
                        self._bump_version()
                    if task.status != target:
                        self.transition(task_id, target)  # transition bumps version
                self._complete_ready_parents()
                self._propagate_result_to_next_sibling(task)
                self._refresh_active_task()
                self._bump_version()
        return task

    def add_artifact(
        self,
        task_id: str,
        *,
        path: str,
        kind: str = "file",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Attach an artifact reference to a task."""
        task = self.get_task(task_id)
        task.artifacts.append({"path": path, "kind": kind, "metadata": metadata or {}})
        self._bump_version()
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
                if task.status != TaskStatus.COMPLETED:
                    return task
                return None
            if task.status != TaskStatus.COMPLETED:
                return task
            return None

        return visit(self.root_task_id)

    def all_done(self) -> bool:
        """Return True only when every task is actually completed."""
        return bool(self.tasks) and all(
            task.status == TaskStatus.COMPLETED for task in self.tasks.values()
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
        become the active task and get scheduled for execution. The synthetic
        result + completion happens in record_reviewer_decision when the
        reviewer approves the executor's verification report.
        """
        for task in self.tasks.values():
            if not task.children or task.status == TaskStatus.COMPLETED:
                continue
            children = [self.tasks[child_id] for child_id in task.children]
            if all(child.status == TaskStatus.COMPLETED for child in children):
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
        if task.result is None:
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
