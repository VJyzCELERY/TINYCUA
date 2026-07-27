"""Generic node handoff tool."""

from __future__ import annotations

import uuid
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
                "Commit ready or analyze with task-bound blocking findings and "
                "nonblocking advisories. Task numbers become canonical IDs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["ready", "analyze"],
                    },
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string"},
                                "finding": {"type": "string", "maxLength": 240},
                            },
                            "required": ["task_id", "finding"],
                            "additionalProperties": False,
                        },
                    },
                    "advisories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string"},
                                "advisory": {"type": "string", "maxLength": 240},
                            },
                            "required": ["task_id", "advisory"],
                            "additionalProperties": False,
                        },
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["decision", "findings", "advisories", "rationale"],
                "additionalProperties": False,
            },
        )
        self._task_store = TaskStateStore()
        self._handoff_store: list[NodeHandoff] | None = None
        self._source_node = "unknown"
        self._assessment_mode = "upfront_decomposition"

    def bind_task_store(self, store: TaskStateStore) -> None:
        """Bind the active session's task state."""
        self._task_store = store

    def bind_handoff_store(self, store: list[NodeHandoff]) -> None:
        """Bind the loop-owned pending handoff store."""
        self._handoff_store = store

    def bind_source_node(self, source_node: str) -> None:
        """Bind the source node ID for the handoff."""
        self._source_node = source_node

    def bind_assessment_mode(self, mode: str) -> None:
        """Bind upfront, local, or final assessment behavior."""
        self._assessment_mode = mode

    def _canonical_records(
        self,
        records: list[dict[str, str]],
        text_field: str,
        *,
        unique_targets: bool = False,
    ) -> tuple[list[dict[str, str]], str | None]:
        """Validate task-bound records without mutating task state."""
        if not isinstance(records, list):
            return [], f"{text_field}s must be an array."
        canonical = []
        for record in records:
            if not isinstance(record, dict):
                return (
                    [],
                    f"Every {text_field} must identify a valid unfinished task.",
                )
            task_ref = record.get("task_id")
            text = record.get(text_field)
            if (
                not isinstance(task_ref, str)
                or not isinstance(text, str)
                or not text.strip()
            ):
                return (
                    [],
                    f"Every {text_field} must identify a valid unfinished task.",
                )
            if len(text.strip()) > 240:
                return [], f"Every {text_field} must be at most 240 characters."
            task_id = self._task_store.resolve_task_id(task_ref)
            task = self._task_store.tasks.get(task_id or "")
            if task is None or task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.SUPERSEDED,
                TaskStatus.COMPROMISED,
            }:
                return [], f"Task {task_ref} must identify a valid unfinished task."
            canonical.append({"task_id": task_id, text_field: text.strip()})
        if unique_targets:
            task_ids = [record["task_id"] for record in canonical]
            if len(task_ids) != len(set(task_ids)):
                return [], "Use at most one blocking finding per task."
        return canonical, None

    def __call__(
        self,
        decision: str,
        findings: list[dict[str, str]],
        advisories: list[dict[str, str]],
        rationale: str,
    ) -> dict[str, Any]:
        """Validate the assessment and emit its canonical analyzer handoff."""
        if decision not in {"ready", "analyze"}:
            return {"success": False, "error": "decision must be ready or analyze."}
        if not isinstance(rationale, str) or not rationale.strip():
            return {"success": False, "error": "rationale is required."}
        canonical_findings, error = self._canonical_records(
            findings, "finding", unique_targets=True
        )
        if error:
            return {"success": False, "error": error}
        canonical_advisories, error = self._canonical_records(advisories, "advisory")
        if error:
            return {"success": False, "error": error}
        if decision == "ready" and canonical_findings:
            return {
                "success": False,
                "error": "ready requires no blocking findings.",
            }
        if decision == "analyze" and not canonical_findings:
            return {
                "success": False,
                "error": "analyze requires at least one blocking finding.",
            }

        assessment_id = uuid.uuid4().hex
        for record in [*canonical_findings, *canonical_advisories]:
            record["assessment_id"] = assessment_id
        exhausted = self._assessment_mode == "final_assessment"
        if exhausted:
            canonical_advisories.extend(
                {
                    "task_id": record["task_id"],
                    "advisory": record["finding"],
                    "assessment_id": assessment_id,
                    "analysis_budget_exhausted": True,
                }
                for record in canonical_findings
            )

        metadata_updates: dict[str, dict[str, Any]] = {}
        if not exhausted:
            for record in canonical_findings:
                task = self._task_store.tasks[record["task_id"]]
                task.metadata.pop("planning_resolution", None)
                metadata_updates.setdefault(record["task_id"], {}).update(
                    {"planning_finding": record, "planning_note": ""}
                )
        for record in canonical_advisories:
            task = self._task_store.tasks[record["task_id"]]
            updates = metadata_updates.setdefault(record["task_id"], {})
            current = list(
                updates.get(
                    "planning_advisories",
                    task.metadata.get("planning_advisories", []),
                )
            )
            updates["planning_advisories"] = [*current, record][-5:]
        for task_id, metadata in metadata_updates.items():
            self._task_store.update_task(task_id, metadata=metadata)

        canonical_ids = list(
            dict.fromkeys(item["task_id"] for item in canonical_findings)
        )

        payload = {
            "decision": decision,
            "selected_task_ids": canonical_ids,
            "findings": canonical_findings,
            "advisories": canonical_advisories,
            "rationale": rationale.strip(),
        }
        if exhausted:
            payload["analysis_budget_exhausted"] = True
        handoff = NodeHandoff(
            source_node=self._source_node,
            target_node="task_analyzer",
            instruction=rationale.strip(),
            payload=payload,
        )
        if self._handoff_store is not None:
            self._handoff_store.append(handoff)
        return {"success": True, **payload, "handoff": handoff.to_dict()}
