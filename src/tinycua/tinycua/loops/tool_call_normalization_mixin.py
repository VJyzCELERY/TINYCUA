"""Tool-call normalization and stable task-reference helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua_sdk.tools.decorators import Tool


class ToolCallNormalizationMixin:
    """Normalize provider calls before tool execution mutates task state."""

    def _normalize_tool_call_arguments(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize provider-emitted argument wrappers without hiding schema data."""
        nested = arguments.get("arguments")
        if set(arguments) != {"arguments"} or not isinstance(nested, dict):
            return arguments
        parameters = getattr(tool, "parameters", {})
        properties = (
            parameters.get("properties", {}) if isinstance(parameters, dict) else {}
        )
        return (
            arguments
            if isinstance(properties, dict) and "arguments" in properties
            else nested
        )

    def _analyzer_batch_task_references(self, node: Node | None) -> dict[str, str]:
        """Snapshot numbered task references for a multi-target analyzer batch."""
        if node is None or node.node_id != "task_analyzer":
            return {}
        if not self._unresolved_analyzer_target_ids(node):
            return {}
        return {
            str(number): task_id
            for number, task_id in self.root_session.task_store.task_number_map().items()
        }

    @staticmethod
    def _freeze_analyzer_task_references(
        arguments: dict[str, Any],
        task_references: dict[str, str],
    ) -> dict[str, Any]:
        """Replace numbered task references with their pre-mutation IDs."""
        if not task_references:
            return arguments
        return {
            key: task_references.get(value, value)
            if key in {"task_id", "parent_id"} and isinstance(value, str)
            else value
            for key, value in arguments.items()
        }

    def _analyzer_planning_targets_for_call(
        self,
        node: Node | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> set[str]:
        """Capture selected targets affected before a task mutation runs."""
        if node is None or node.node_id != "task_analyzer":
            return set()
        unresolved = self._unresolved_analyzer_target_ids(node)
        if not unresolved:
            return set()
        store = self.root_session.task_store
        refs: list[Any]
        if tool_name == "task_update":
            task_ref = arguments.get("task_id")
            refs = [store.active_task_id if task_ref is None else task_ref]
        elif tool_name == "task_create":
            refs = [arguments.get("parent_id")]
        elif tool_name == "task_decompose":
            refs = [arguments.get("task_id")]
        elif tool_name == "task_shrink":
            refs = [arguments.get("task_id")]
            if arguments.get("action") == "merge":
                refs.append(arguments.get("parent_id"))
        else:
            return set()
        candidates = [
            store.resolve_task_id(ref) for ref in refs if isinstance(ref, str)
        ]
        if tool_name == "task_update":
            return (
                {candidates[0]} if candidates and candidates[0] in unresolved else set()
            )
        return {
            target_id
            for target_id in unresolved
            if any(
                candidate is not None and self._task_is_in_subtree(candidate, target_id)
                for candidate in candidates
            )
        }
