"""Generic node handoff tool."""

from __future__ import annotations

from typing import Any

from tinycua.config.types import Tool
from tinycua.models.node_handoff import NodeHandoff


class NodeHandoffTool(Tool):
    """Tool for emitting an explicit handoff to another node."""

    def __init__(self) -> None:
        super().__init__(
            name="node_handoff",
            description=(
                "Emit a generic final handoff instruction and payload for the "
                "next node. Use this instead of mutating unrelated state."
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
