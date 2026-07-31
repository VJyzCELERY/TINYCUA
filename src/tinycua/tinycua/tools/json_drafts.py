"""Session-scoped file-backed JSON drafts for structured tool commits."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from tinycua.config.types import Tool

MAX_DRAFT_BYTES = 64 * 1024


class _JsonDraftTool(Tool):
    """Base class for tools bound to one node execution's draft store."""

    def __init__(self, name: str, parameters: dict[str, Any]) -> None:
        super().__init__(name=name, parameters=parameters)
        self._drafts: dict[str, dict[str, Any]] = {}
        self._session_id = ""
        self._node_id = ""
        self._task_version = 0
        self._allowed_targets: set[str] = set()
        self._workspace_dir: Path | None = None
        self._execution_id = ""

    def bind_json_drafts(
        self,
        drafts: dict[str, dict[str, Any]],
        session_id: str,
        node_id: str,
        task_version: int,
        allowed_targets: set[str],
        workspace_dir: Path | None,
        execution_id: str | None = None,
    ) -> None:
        """Bind the current session, workspace, and node execution."""
        self._drafts = drafts
        self._session_id = session_id
        self._node_id = node_id
        self._task_version = task_version
        self._allowed_targets = allowed_targets
        self._workspace_dir = workspace_dir.resolve() if workspace_dir else None
        self._execution_id = execution_id or node_id

    def _draft(self, draft_id: str) -> dict[str, Any] | None:
        draft = self._drafts.get(draft_id)
        if draft is None:
            return None
        if (
            draft["session_id"] != self._session_id
            or draft["node_id"] != self._node_id
            or draft["execution_id"] != self._execution_id
        ):
            return None
        return draft

    def _path(self, draft: dict[str, Any]) -> Path | None:
        if self._workspace_dir is None:
            return None
        path = (self._workspace_dir / draft["path"]).resolve()
        if not path.is_relative_to(self._workspace_dir):
            return None
        return path


class JsonDraftCreateTool(_JsonDraftTool):
    """Create the one runtime-selected file draft for this node execution."""

    def __init__(self) -> None:
        super().__init__(
            "json_draft_create",
            {
                "type": "object",
                "properties": {"target_tool": {"type": "string"}},
                "required": ["target_tool"],
                "additionalProperties": False,
            },
        )

    def __call__(self, target_tool: str) -> dict[str, Any]:
        """Create an empty object draft for a currently available target."""
        if target_tool not in self._allowed_targets:
            return {"success": False, "error": "target_tool_not_available"}
        if self._workspace_dir is None:
            return {"success": False, "error": "workspace_not_available"}
        if any(
            draft["session_id"] == self._session_id
            and draft["node_id"] == self._node_id
            and draft["execution_id"] == self._execution_id
            for draft in self._drafts.values()
        ):
            return {"success": False, "error": "active_draft_exists"}
        draft_id = uuid.uuid4().hex
        path = (
            Path(".tinycua")
            / self._session_id
            / "tmp"
            / self._execution_id
            / f"{draft_id}.json"
        )
        try:
            absolute_path = (self._workspace_dir / path).resolve()
            if not absolute_path.is_relative_to(self._workspace_dir):
                return {"success": False, "error": "invalid_draft_path"}
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            with absolute_path.open("x", encoding="utf-8") as draft_file:
                draft_file.write("{}\n")
        except OSError as exc:
            return {"success": False, "error": f"draft_create_failed: {exc}"}
        self._drafts[draft_id] = {
            "session_id": self._session_id,
            "node_id": self._node_id,
            "execution_id": self._execution_id,
            "task_version": self._task_version,
            "target_tool": target_tool,
            "path": str(path),
        }
        return {
            "success": True,
            "draft_id": draft_id,
            "target_tool": target_tool,
            "path": str(path),
        }


class JsonDraftCommitTool(_JsonDraftTool):
    """Parse and prepare a managed draft for canonical tool execution."""

    def __init__(self) -> None:
        super().__init__(
            "json_draft_commit",
            {
                "type": "object",
                "properties": {"draft_id": {"type": "string"}},
                "required": ["draft_id"],
                "additionalProperties": False,
            },
        )

    def __call__(self, draft_id: str) -> dict[str, Any]:
        """Read the managed file and return parsed target arguments."""
        draft = self._draft(draft_id)
        if draft is None:
            return {"success": False, "error": "draft_not_found"}
        if draft["task_version"] != self._task_version:
            return {"success": False, "error": "stale_draft_task_state"}
        if draft["target_tool"] not in self._allowed_targets:
            return {"success": False, "error": "target_tool_not_available"}
        path = self._path(draft)
        if path is None or not path.is_file():
            return {"success": False, "error": "draft_file_not_found"}
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return {"success": False, "error": f"draft_read_failed: {exc}"}
        if len(content.encode()) > MAX_DRAFT_BYTES:
            return {"success": False, "error": "draft_too_large"}
        try:
            arguments = json.loads(content)
        except json.JSONDecodeError as exc:
            return {
                "success": False,
                "error": f"invalid_json line={exc.lineno} column={exc.colno}",
            }
        if not isinstance(arguments, dict):
            return {"success": False, "error": "draft_json_must_be_object"}
        return {
            "success": True,
            "draft_id": draft_id,
            "target_tool": draft["target_tool"],
            "arguments": arguments,
        }

    def consume(self, draft_id: str) -> None:
        """Delete a draft only after its target mutation succeeds."""
        draft = self._draft(draft_id)
        if draft is None:
            return
        path = self._path(draft)
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                return
        self._drafts.pop(draft_id, None)
