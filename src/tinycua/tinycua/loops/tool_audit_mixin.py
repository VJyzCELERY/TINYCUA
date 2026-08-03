"""Tool-audit and evidence enrichment helpers for TinyCUALoop.

Extracted from ``tinycua_loop.py`` to keep it inside the LOC acceptance gate;
composed into ``TinyCUALoop`` via MRO like the other loop mixins.
"""

from __future__ import annotations

import json
from typing import Any


class ToolAuditMixin:
    """Write per-tool audit JSON and attach evidence to executor results."""

    def _write_tool_audit_artifact(
        self,
        name: str,
        arguments: dict[str, Any],
        output: Any,
    ) -> str | None:
        """Write a durable audit JSON for action/research tool calls."""
        if self.artifact_dir is None or self._disable_tool_audit:
            return None
        if name not in {
            "run_shell",
            "run_python",
            "web_search",
            "fetch_url",
            "search_files",
        }:
            return None
        self._tool_artifact_seq += 1
        audit_dir = self.artifact_dir / "tool-calls"
        audit_dir.mkdir(parents=True, exist_ok=True)
        path = audit_dir / f"{self._tool_artifact_seq:04d}-{name}.json"
        path.write_text(
            json.dumps(
                {"name": name, "arguments": arguments, "output": output},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return str(path)

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
