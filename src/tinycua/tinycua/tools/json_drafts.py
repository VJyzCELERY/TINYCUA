"""Session-scoped editable JSON drafts for structured tool commits."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from tinycua.config.types import Tool

MAX_DRAFT_BYTES = 64 * 1024
MAX_DRAFTS = 8


class _JsonDraftTool(Tool):
    """Base class for tools bound to one node's session draft store."""

    def __init__(self, name: str, parameters: dict[str, Any]) -> None:
        super().__init__(name=name, parameters=parameters)
        self._drafts: dict[str, dict[str, Any]] = {}
        self._session_id = ""
        self._node_id = ""
        self._task_version = 0
        self._allowed_targets: set[str] = set()

    def bind_json_drafts(
        self,
        drafts: dict[str, dict[str, Any]],
        session_id: str,
        node_id: str,
        task_version: int,
        allowed_targets: set[str],
    ) -> None:
        """Bind the draft store and current node ownership constraints."""
        self._drafts = drafts
        self._session_id = session_id
        self._node_id = node_id
        self._task_version = task_version
        self._allowed_targets = allowed_targets

    def _draft(self, draft_id: str) -> dict[str, Any] | None:
        draft = self._drafts.get(draft_id)
        if draft is None:
            return None
        if draft["session_id"] != self._session_id or draft["node_id"] != self._node_id:
            return None
        return draft

    @staticmethod
    def _summary(draft_id: str, draft: dict[str, Any]) -> dict[str, Any]:
        content = draft["content"]
        return {
            "success": True,
            "draft_id": draft_id,
            "target_tool": draft["target_tool"],
            "revision": draft["revision"],
            "chars": len(content),
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }


class JsonDraftCreateTool(_JsonDraftTool):
    """Create a session-local draft for a currently available structured tool."""

    def __init__(self) -> None:
        super().__init__(
            "json_draft_create",
            {
                "type": "object",
                "properties": {
                    "target_tool": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["target_tool", "content"],
                "additionalProperties": False,
            },
        )

    def __call__(self, target_tool: str, content: str) -> dict[str, Any]:
        """Create a draft without requiring it to be valid JSON yet."""
        if target_tool not in self._allowed_targets:
            return {"success": False, "error": "target_tool_not_available"}
        if len(content.encode()) > MAX_DRAFT_BYTES:
            return {"success": False, "error": "draft_too_large"}
        if len(self._drafts) >= MAX_DRAFTS:
            return {"success": False, "error": "draft_limit_reached"}
        draft_id = uuid.uuid4().hex
        draft = {
            "session_id": self._session_id,
            "node_id": self._node_id,
            "task_version": self._task_version,
            "target_tool": target_tool,
            "content": content,
            "revision": 0,
        }
        self._drafts[draft_id] = draft
        return self._summary(draft_id, draft)


class JsonDraftReadTool(_JsonDraftTool):
    """Read a bounded slice of an owned JSON draft."""

    def __init__(self) -> None:
        super().__init__(
            "json_draft_read",
            {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 8192},
                },
                "required": ["draft_id"],
                "additionalProperties": False,
            },
        )

    def __call__(
        self, draft_id: str, offset: int = 0, limit: int = 4096
    ) -> dict[str, Any]:
        """Return one bounded draft slice and its revision metadata."""
        draft = self._draft(draft_id)
        if draft is None:
            return {"success": False, "error": "draft_not_found"}
        offset = max(0, int(offset))
        limit = min(8192, max(1, int(limit)))
        result = self._summary(draft_id, draft)
        result["content"] = draft["content"][offset : offset + limit]
        result["offset"] = offset
        return result


class JsonDraftReplaceTool(_JsonDraftTool):
    """Make one exact, revision-checked replacement in a JSON draft."""

    def __init__(self) -> None:
        super().__init__(
            "json_draft_replace",
            {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "expected_revision": {"type": "integer", "minimum": 0},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": [
                    "draft_id",
                    "expected_revision",
                    "old_string",
                    "new_string",
                ],
                "additionalProperties": False,
            },
        )

    def __call__(
        self,
        draft_id: str,
        expected_revision: int,
        old_string: str,
        new_string: str,
    ) -> dict[str, Any]:
        """Replace exactly one literal occurrence without fuzzy matching."""
        draft = self._draft(draft_id)
        if draft is None:
            return {"success": False, "error": "draft_not_found"}
        if draft["revision"] != expected_revision:
            return {"success": False, "error": "stale_draft_revision"}
        if not old_string or draft["content"].count(old_string) != 1:
            return {"success": False, "error": "old_string_must_match_exactly_once"}
        content = draft["content"].replace(old_string, new_string, 1)
        if len(content.encode()) > MAX_DRAFT_BYTES:
            return {"success": False, "error": "draft_too_large"}
        draft["content"] = content
        draft["revision"] += 1
        return self._summary(draft_id, draft)


class JsonDraftCommitTool(_JsonDraftTool):
    """Parse and prepare a draft for canonical target-tool execution."""

    def __init__(self) -> None:
        super().__init__(
            "json_draft_commit",
            {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "expected_revision": {"type": "integer", "minimum": 0},
                },
                "required": ["draft_id", "expected_revision"],
                "additionalProperties": False,
            },
        )

    def __call__(self, draft_id: str, expected_revision: int) -> dict[str, Any]:
        """Return parsed target arguments; the loop performs the real commit."""
        draft = self._draft(draft_id)
        if draft is None:
            return {"success": False, "error": "draft_not_found"}
        if draft["revision"] != expected_revision:
            return {"success": False, "error": "stale_draft_revision"}
        if draft["task_version"] != self._task_version:
            return {"success": False, "error": "stale_draft_task_state"}
        if draft["target_tool"] not in self._allowed_targets:
            return {"success": False, "error": "target_tool_not_available"}
        try:
            arguments = json.loads(draft["content"])
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

    def consume(self, draft_id: str, expected_revision: int) -> None:
        """Delete a draft only after its target mutation succeeds."""
        draft = self._draft(draft_id)
        if draft is not None and draft["revision"] == expected_revision:
            self._drafts.pop(draft_id, None)
