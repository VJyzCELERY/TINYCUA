"""Tool-audit and evidence enrichment helpers for TinyCUALoop.

Extracted from ``tinycua_loop.py`` to keep it inside the LOC acceptance gate;
composed into ``TinyCUALoop`` via MRO like the other loop mixins.
"""

from __future__ import annotations

from typing import Any


class ToolAuditMixin:
    """Write per-tool audit JSON and attach evidence to executor results."""

    def _write_tool_audit_artifact(
        self,
        name: str,
        arguments: dict[str, Any],
        output: Any,
    ) -> str | None:
        """Disable duplicate workspace-local raw tool transcripts."""
        del name, arguments, output
        return None

    def _enrich_task_results_from_tool_batch(
        self,
        node: Any,
        tool_results: list[dict[str, Any]],
    ) -> None:
        """Attach tool-call transcript evidence to recorded task results."""
        if node.node_id != "task_executor":
            return
        for item in tool_results:
            if item.get("name") != "task_result_update":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("success") is not True:
                continue
            task_id = output.get("task_id")
            if not isinstance(task_id, str):
                continue
            try:
                task = self.root_session.task_store.get_task(task_id)
            except ValueError:
                continue
            result = task.result
            partial_results = list(
                task.metadata.get("executor_partial_tool_results", [])
            )
            merged_tool_results = [*partial_results, *tool_results]
            evidence = self._json_safe(merged_tool_results)
            if result is not None:
                result.metadata["tool_results"] = evidence
                task.metadata.pop("executor_partial_tool_results", None)
