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
