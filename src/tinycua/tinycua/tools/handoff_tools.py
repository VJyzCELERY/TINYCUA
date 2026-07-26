"""Generic node handoff tool."""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool
from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.task import TaskStateStore, TaskStatus


class NodeHandoffTool(Tool):
    """Tool for emitting an explicit handoff to another node."""

    def __init__(self) -> None:
        super().__init__(
            name="node_handoff",
            description=(
                "Send scoped instructions and payload to a different agent. The "
                "recipient receives this handoff, not your conversation or reasoning; "
                "include the task IDs, decision, evidence, and constraints it needs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target_node": {"type": "string"},
                    "instruction": {"type": "string"},
                    "payload": {"type": "object"},
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "metadata": {"type": "object"},
                },
                "required": ["instruction"],
                "additionalProperties": False,
            },
        )
        self._store: list[NodeHandoff] | None = None
        self._source_node = "unknown"

    def bind_handoff_store(self, store: list[NodeHandoff]) -> None:
        """Bind this tool to the loop-owned pending handoff store."""
        self._store = store

    def bind_source_node(self, source_node: str) -> None:
        """Bind the source node ID for produced handoffs."""
        self._source_node = source_node

    def __call__(
        self,
        instruction: str,
        target_node: str | None = None,
        payload: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and store a generic handoff."""
        if not instruction.strip():
            return {"success": False, "error": "instruction is required"}
        handoff = NodeHandoff(
            source_node=self._source_node,
            target_node=target_node,
            instruction=instruction.strip(),
            payload=payload or {},
            constraints=constraints or [],
            metadata=metadata or {},
        )
        if self._store is not None:
            self._store.append(handoff)
        return {"success": True, "handoff": handoff.to_dict()}


class TaskAssessmentDecisionTool(Tool):
    """Validate and hand off a TaskAssessor readiness decision."""

    def __init__(self) -> None:
        super().__init__(
            name="task_assessment_decision",
            description=(
                "Commit TaskAssessor's roadmap decision. Use ready only with no "
                "selected tasks; use analyze with one or more unfinished task IDs. "
                "Task numbers are accepted and converted to canonical IDs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["ready", "analyze"],
                    },
                    "selected_task_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["decision", "selected_task_ids", "rationale"],
                "additionalProperties": False,
            },
        )
        self._task_store = TaskStateStore()
        self._handoff_store: list[NodeHandoff] | None = None
        self._source_node = "unknown"

    def bind_task_store(self, store: TaskStateStore) -> None:
        """Bind the active session's task state."""
        self._task_store = store

    def bind_handoff_store(self, store: list[NodeHandoff]) -> None:
        """Bind the loop-owned pending handoff store."""
        self._handoff_store = store

    def bind_source_node(self, source_node: str) -> None:
        """Bind the source node ID for the handoff."""
        self._source_node = source_node

    def __call__(
        self,
        decision: str,
        selected_task_ids: list[str],
        rationale: str,
    ) -> dict[str, Any]:
        """Validate the assessment and emit its canonical analyzer handoff."""
        if decision not in {"ready", "analyze"}:
            return {"success": False, "error": "decision must be ready or analyze."}
        if not isinstance(rationale, str) or not rationale.strip():
            return {"success": False, "error": "rationale is required."}
        if not isinstance(selected_task_ids, list) or any(
            not isinstance(task_id, str) for task_id in selected_task_ids
        ):
            return {
                "success": False,
                "error": "selected_task_ids must be an array of task IDs.",
            }
        if decision == "ready" and selected_task_ids:
            return {
                "success": False,
                "error": "ready requires an empty selected_task_ids array.",
            }
        if decision == "analyze" and not selected_task_ids:
            return {
                "success": False,
                "error": "analyze requires a nonempty selected_task_ids array.",
            }

        canonical_ids: list[str] = []
        for task_ref in selected_task_ids:
            task_id = self._task_store.resolve_task_id(task_ref)
            task = self._task_store.tasks.get(task_id or "")
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.SUPERSEDED,
                TaskStatus.COMPROMISED,
            }:
                return {
                    "success": False,
                    "error": f"Task {task_ref} must identify a valid unfinished task.",
                }
            if task_id not in canonical_ids:
                canonical_ids.append(task_id)

        payload = {
            "decision": decision,
            "selected_task_ids": canonical_ids,
            "rationale": rationale.strip(),
        }
        handoff = NodeHandoff(
            source_node=self._source_node,
            target_node="task_analyzer",
            instruction=rationale.strip(),
            payload=payload,
        )
        if self._handoff_store is not None:
            self._handoff_store.append(handoff)
        return {"success": True, **payload, "handoff": handoff.to_dict()}
