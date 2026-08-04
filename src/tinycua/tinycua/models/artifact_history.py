"""Session artifact history: workspace manifests, revisions, and review checkpoints.

The store owns a content-addressed revision trail for workspace writes that
happen through the shared tool execution boundary, plus logical task-result
revisions and the review checkpoint. Everything is opaque: model-visible
projections receive revision IDs and relative paths, never the internal
session storage directory.

Storage is stdlib-only. When ``session_dir`` is set, revisions and eligible
blobs persist under it; otherwise the store is session-local in memory (the
unit-test and embedding default). Failure behavior is fail-closed: an
unreadable workspace blocks pre-mutation capture, and a post-write persistence
failure marks the audit incomplete so review approval is refused.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Directories owned by TinyCUA or its harnesses that must never be captured
#: into workspace manifests (they are either internal state or disposable).
_EXCLUDED_DIRNAMES = frozenset(
    {
        ".tinycua",
        ".tinycua-artifacts",
        ".tinycua_context_cache",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".agents",
        "tmp",
    }
)
_CONTENT_LIMIT = 1_000_000  # bytes; larger files stay hash-only.
_INSPECT_PAGE_LIMIT = 8_000


def _sha256_text(value: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(value).hexdigest()


def _hash_file(path: Path) -> tuple[str, int]:
    """Return (sha256 hex, size) for a regular file."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _is_binary(path: Path) -> bool:
    """Return whether a file's head is not valid UTF-8 text."""
    try:
        with path.open("rb") as handle:
            head = handle.read(8_192)
    except OSError:
        return True
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _is_sensitive_path(relative: str) -> bool:
    """Return whether a relative path should stay hash-only."""
    filename = relative.rsplit("/", 1)[-1].lower()
    return any(part.startswith(".") for part in relative.split("/")) or (
        filename
        in {
            "env",
            "environment",
            "id_dsa",
            "id_ecdsa",
            "id_ed25519",
            "id_rsa",
            "private-key",
            "private_key",
        }
        or any(token in filename for token in ("credential", "secret", "token"))
    )


class SessionArtifactStore:
    """Own one session's workspace and result revision history.

    Args:
        session_dir: Optional system-owned storage directory outside the
            workspace. When ``None`` the store is in-memory only.
        workspace_dir: The judged workspace whose writes are captured. When
            ``None`` the store captures nothing (embedded no-workspace runs).
    """

    content_limit = _CONTENT_LIMIT

    def __init__(
        self,
        *,
        session_dir: Path | None = None,
        workspace_dir: Path | None = None,
    ) -> None:
        if workspace_dir is not None:
            workspace_dir = Path(workspace_dir).expanduser().resolve()
        if session_dir is not None:
            session_dir = Path(session_dir).expanduser().resolve()
            if workspace_dir is not None:
                try:
                    session_dir.relative_to(workspace_dir)
                except ValueError:
                    pass
                else:
                    msg = "Session storage must be outside the workspace directory."
                    raise ValueError(msg)
        self._root = session_dir
        self._workspace_dir = workspace_dir
        self._revisions: list[dict[str, Any]] = []
        self._blobs: dict[str, bytes] = {}
        self._result_revisions: dict[str, str] = {}
        self._checkpoint: dict[str, Any] | None = None
        self._incomplete = False
        self._incomplete_reason: str | None = None
        self._pending_before: dict[str, dict[str, Any]] | None = None

    # -- capture lifecycle ---------------------------------------------------

    def begin_capture(self) -> str | None:
        """Capture the pre-mutation manifest; return an error when fail-closed.

        An unreadable workspace or unavailable session storage blocks the
        caller (the tool is not executed) so no untracked mutation can occur.
        """
        if self._incomplete:
            return "artifact capture unavailable"
        error = self._ensure_root_writable()
        if error is not None:
            return error
        try:
            self._pending_before = self._scan_workspace()
        except OSError as exc:
            self._mark_incomplete(f"workspace scan failed: {exc}")
            return "artifact capture unavailable"
        return None

    def finish_capture(self, provenance: dict[str, Any]) -> dict[str, Any] | None:
        """Compare pre/post state and append one revision when state changed.

        Args:
            provenance: Tool-call identity (``tool_name``, ``call_id``,
                ``success``, optional ``error``).

        Returns:
            The new revision, or ``None`` for a no-op call.
        """
        before = self._pending_before
        self._pending_before = None
        try:
            if before is None:
                before = self._scan_workspace()
            after = self._scan_workspace()
        except OSError as exc:
            self._mark_incomplete(f"workspace rescan failed: {exc}")
            return None
        changes = self._diff_manifests(before, after)
        if not changes:
            return None
        self._store_eligible_blobs(changes)
        revision = self._build_revision(changes, dict(provenance))
        self._revisions.append(revision)
        self._persist_revision(revision)
        return dict(revision)

    # -- result revisions ----------------------------------------------------

    def record_result_revision(self, task_id: str, result: Any) -> dict[str, str]:
        """Store a content-addressed logical result revision before replacement.

        Args:
            task_id: Owning task id.
            result: A :class:`TaskResult` or a plain string report.

        Returns:
            ``{"revision_id", "content_hash", "task_id"}``.
        """
        if not isinstance(task_id, str) or not task_id.strip():
            msg = "Result revision requires a valid task id."
            raise ValueError(msg)
        content = getattr(result, "content", None)
        if content is None:
            content = result
        if not isinstance(content, str) or not content.strip():
            msg = "Result revision requires non-empty report content."
            raise ValueError(msg)
        content_hash = _sha256_text(content)
        self._result_revisions.setdefault(content_hash, content)
        if self._root is not None:
            try:
                result_dir = self._root / "results"
                result_dir.mkdir(parents=True, exist_ok=True)
                (result_dir / content_hash).write_text(content, encoding="utf-8")
            except OSError as exc:
                self._mark_incomplete(f"failed to persist result revision: {exc}")
                raise OSError("Could not persist reviewed result.") from None
        return {
            "revision_id": f"result-{content_hash}",
            "content_hash": content_hash,
            "task_id": task_id,
        }

    # -- review checkpoint ---------------------------------------------------

    def checkpoint(self) -> dict[str, Any] | None:
        """Return the last committed review checkpoint, or ``None``."""
        if self._checkpoint is None:
            return None
        return dict(self._checkpoint)

    def prepare_checkpoint(self, task_id: str, review_event_id: str) -> dict[str, Any]:
        """Durably prepare a checkpoint before publishing its review verdict."""
        checkpoint = {
            "task_id": task_id,
            "review_event_id": review_event_id,
            "revision_id": self.latest_revision_id() or "none",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._root is not None:
            try:
                (self._root / "checkpoint.json").write_text(
                    json.dumps(checkpoint, indent=2), encoding="utf-8"
                )
            except OSError as exc:
                self._mark_incomplete(f"failed to persist checkpoint: {exc}")
                raise OSError("Could not persist review checkpoint.") from None
        return checkpoint

    def advance_checkpoint(self, task_id: str, review_event_id: str) -> dict[str, Any]:
        """Advance the in-memory checkpoint after durable preparation."""
        checkpoint = self.prepare_checkpoint(task_id, review_event_id)
        self.commit_prepared_checkpoint(checkpoint)
        return dict(checkpoint)

    def commit_prepared_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Publish an already durable checkpoint in memory."""
        self._checkpoint = dict(checkpoint)

    def current_range(self) -> dict[str, str]:
        """Return the reviewed artifact range for the next committed verdict."""
        checkpoint_revision = (
            self._checkpoint.get("revision_id") if self._checkpoint else None
        )
        return {
            "from": checkpoint_revision or "baseline",
            "to": self.latest_revision_id() or "none",
        }

    def changes_since_checkpoint(self) -> dict[str, Any]:
        """Return cumulative changed-path projection since the last checkpoint."""
        checkpoint_revision = (
            self._checkpoint.get("revision_id") if self._checkpoint else None
        )
        revisions = list(self._revisions)
        if checkpoint_revision not in {None, "none"}:
            after_index = None
            for index, revision in enumerate(revisions):
                if revision["revision_id"] == checkpoint_revision:
                    after_index = index + 1
                    break
            if after_index is not None:
                revisions = revisions[after_index:]
            else:
                revisions = []
        by_path: dict[str, dict[str, Any]] = {}
        for revision in revisions:
            for change in revision["changes"]:
                by_path[change["path"]] = {
                    **change,
                    "revision_id": revision["revision_id"],
                }
        return {
            "from_revision": checkpoint_revision or "baseline",
            "to_revision": revisions[-1]["revision_id"] if revisions else "none",
            "revision_ids": [revision["revision_id"] for revision in revisions],
            "changes": [dict(change) for change in by_path.values()],
        }

    def render_checkpoint_diff(self, *, limit: int = 40) -> str:
        """Render the bounded cumulative changed-path projection for Reviewers."""
        diff = self.changes_since_checkpoint()
        changes = diff["changes"]
        if not changes:
            return ""
        lines = [
            "## Artifacts changed since last review checkpoint "
            f"({diff['from_revision']} -> {diff['to_revision']})"
        ]
        for change in changes[:limit]:
            after = change.get("after") or {}
            if change["status"] == "deleted":
                before_hash = str((change.get("before") or {}).get("hash", ""))
                lines.append(f"- deleted {change['path']} (was {before_hash[:12]})")
            else:
                lines.append(
                    f"- {change['status']} {change['path']} (revision_id={change['revision_id']}) "
                    f"(size={after.get('size')}, hash={str(after.get('hash', ''))[:12]})"
                )
        remaining = len(changes) - limit
        if remaining > 0:
            lines.append(
                f"- ... {remaining} more changed paths (opaque detail by revision_id)"
            )
        return "\n".join(lines)

    # -- opaque inspection ---------------------------------------------------

    def inspect_revision(
        self,
        revision_id: str,
        *,
        path: str | None = None,
        offset: int = 0,
        limit: int = 4_000,
    ) -> dict[str, Any]:
        """Return bounded, opaque revision detail without exposing storage paths.

        Args:
            revision_id: Opaque ``rev-...`` identifier.
            path: Optional relative path to page changed content for.
            offset: Zero-based character offset.
            limit: Character/page count bounds.

        Returns:
            A bounded projection: change summaries, or one paged content slice.
        """
        if not isinstance(revision_id, str) or not revision_id.strip():
            msg = "revision_id is required."
            raise ValueError(msg)
        revision = next(
            (item for item in self._revisions if item["revision_id"] == revision_id),
            None,
        )
        if revision is None:
            msg = f"Unknown revision: {revision_id}"
            raise ValueError(msg)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            msg = "inspection offset must be a non-negative integer."
            raise ValueError(msg)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= _INSPECT_PAGE_LIMIT
        ):
            msg = "inspection limit must be between 1 and 8000."
            raise ValueError(msg)
        if path is not None:
            return self._inspect_path(revision, str(path), offset, limit)
        end = min(offset + limit, len(revision["changes"]))
        return {
            "revision_id": revision["revision_id"],
            "sequence": revision["sequence"],
            "parent": revision["parent"],
            "provenance": dict(revision["provenance"]),
            "tree_hash": revision["tree_hash"],
            "total_changes": len(revision["changes"]),
            "changes": [
                {
                    "path": change["path"],
                    "status": change["status"],
                    "before": change["before"],
                    "after": change["after"],
                }
                for change in revision["changes"][offset:end]
            ],
            "offset": offset,
            "limit": limit,
            "next_offset": end if end < len(revision["changes"]) else None,
            "has_more": end < len(revision["changes"]),
        }

    def inspect_result_revision(
        self, revision_id: str, *, offset: int = 0, limit: int = 4_000
    ) -> dict[str, Any]:
        """Return a bounded page of one persisted reviewed result."""
        if not isinstance(revision_id, str) or not revision_id.startswith("result-"):
            raise ValueError("Unknown result revision.")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("inspection offset must be a non-negative integer.")
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= _INSPECT_PAGE_LIMIT
        ):
            raise ValueError("inspection limit must be between 1 and 8000.")
        content_hash = revision_id.removeprefix("result-")
        content = self._result_revisions.get(content_hash)
        if content is None and self._root is not None:
            try:
                content = (self._root / "results" / content_hash).read_text(
                    encoding="utf-8"
                )
            except OSError as exc:
                raise ValueError("Reviewed result is unavailable.") from exc
        if content is None:
            raise ValueError("Unknown result revision.")
        end = min(offset + limit, len(content))
        return {
            "revision_id": revision_id,
            "content": content[offset:end],
            "offset": offset,
            "limit": limit,
            "total_chars": len(content),
            "next_offset": end if end < len(content) else None,
            "has_more": end < len(content),
        }

    def _inspect_path(
        self, revision: dict[str, Any], path: str, offset: int, limit: int
    ) -> dict[str, Any]:
        """Return one bounded content page for a single changed path."""
        change = next(
            (item for item in revision["changes"] if item["path"] == path), None
        )
        if change is None:
            msg = f"Path not changed in revision {revision['revision_id']}: {path}"
            raise ValueError(msg)
        blob_id = (change.get("after") or {}).get("blob_id")
        content = self._blobs.get(blob_id, b"") if blob_id else b""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        end = min(offset + limit, len(content))
        return {
            "revision_id": revision["revision_id"],
            "path": path,
            "status": change["status"],
            "content": content[offset:end],
            "offset": offset,
            "limit": limit,
            "total_chars": len(content),
            "next_offset": end if end < len(content) else None,
            "has_more": end < len(content),
        }

    # -- failure state -------------------------------------------------------

    def is_incomplete(self) -> bool:
        """Return whether any audit write is missing after a failure."""
        return self._incomplete

    def incomplete_reason(self) -> str | None:
        """Return the surfaced persistence-failure reason, or ``None``."""
        return self._incomplete_reason

    def _mark_incomplete(self, reason: str) -> None:
        """Record an explicit audit failure without discarding in-memory data."""
        self._incomplete = True
        self._incomplete_reason = reason
        if self._root is not None:
            try:
                (self._root / "incomplete.json").write_text(
                    json.dumps({"reason": reason}, indent=2), encoding="utf-8"
                )
            except OSError:
                pass

    # -- read helpers --------------------------------------------------------

    def revisions(self) -> list[dict[str, Any]]:
        """Return the ordered revision events."""
        return [dict(revision) for revision in self._revisions]

    def revision_count(self) -> int:
        """Return the number of captured revisions."""
        return len(self._revisions)

    def latest_revision_id(self) -> str | None:
        """Return the latest revision id, or ``None`` when none exist."""
        if not self._revisions:
            return None
        return self._revisions[-1]["revision_id"]

    def blob_hashes(self) -> list[str]:
        """Return stored content blob hashes."""
        return list(self._blobs)

    def blob_content(self, blob_id: str) -> bytes | None:
        """Return stored blob content by hash, or ``None``."""
        return self._blobs.get(blob_id)

    # -- internals -----------------------------------------------------------

    def _ensure_root_writable(self) -> str | None:
        """Fail closed when session storage cannot be made writable."""
        if self._root is None:
            return None
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            probe = self._root / ".write-test"
            probe.touch()
            probe.unlink()
        except OSError as exc:
            self._mark_incomplete(f"session storage unavailable: {exc}")
            return "artifact capture unavailable"
        return None

    def _scan_workspace(self) -> dict[str, dict[str, Any]]:
        """Return a safe manifest of workspace paths, hashes, and sizes."""
        if self._workspace_dir is None:
            return {}
        if not self._workspace_dir.is_dir():
            msg = f"Workspace is not a directory: {self._workspace_dir}"
            raise NotADirectoryError(msg)
        manifest: dict[str, dict[str, Any]] = {}
        for dirpath, dirnames, filenames in os.walk(self._workspace_dir):
            kept_dirs = []
            for name in sorted(dirnames):
                if name in _EXCLUDED_DIRNAMES:
                    continue
                full = Path(dirpath) / name
                relative = full.relative_to(self._workspace_dir).as_posix()
                if full.is_symlink():
                    target = os.readlink(full)
                    manifest[relative] = {
                        "kind": "symlink",
                        "target": str(target),
                        "hash": _sha256_text(str(target)),
                        "size": len(str(target)),
                        "eligible": False,
                    }
                else:
                    kept_dirs.append(name)
            dirnames[:] = kept_dirs
            for name in sorted(filenames):
                full = Path(dirpath) / name
                relative = full.relative_to(self._workspace_dir).as_posix()
                try:
                    if full.is_symlink():
                        target = os.readlink(full)
                        manifest[relative] = {
                            "kind": "symlink",
                            "target": str(target),
                            "hash": _sha256_text(str(target)),
                            "size": len(str(target)),
                            "eligible": False,
                        }
                        continue
                    digest, size = _hash_file(full)
                    manifest[relative] = {
                        "kind": "file",
                        "hash": digest,
                        "size": size,
                        "eligible": (
                            not _is_sensitive_path(relative)
                            and size <= _CONTENT_LIMIT
                            and not _is_binary(full)
                        ),
                    }
                except OSError:
                    raise
        return manifest

    @staticmethod
    def _diff_manifests(
        before: dict[str, dict[str, Any]],
        after: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return path changes between two manifests."""
        changes: list[dict[str, Any]] = []
        for relative, info in after.items():
            prior = before.get(relative)
            if prior is None:
                changes.append(
                    {
                        "path": relative,
                        "status": "added",
                        "before": None,
                        "after": SessionArtifactStore._change_record(info),
                    }
                )
            elif prior != info:
                changes.append(
                    {
                        "path": relative,
                        "status": "modified",
                        "before": SessionArtifactStore._change_record(prior),
                        "after": SessionArtifactStore._change_record(info),
                    }
                )
        for relative, info in before.items():
            if relative not in after:
                changes.append(
                    {
                        "path": relative,
                        "status": "deleted",
                        "before": SessionArtifactStore._change_record(info),
                        "after": None,
                    }
                )
        return changes

    @staticmethod
    def _change_record(info: dict[str, Any]) -> dict[str, Any]:
        """Build a path change record; blobs are attached when eligible."""
        record: dict[str, Any] = {
            "hash": info.get("hash"),
            "size": info.get("size"),
        }
        if info.get("kind") == "symlink":
            record["kind"] = "symlink"
            record["blob_id"] = None
        elif info.get("eligible"):
            record["blob_id"] = info.get("hash")
        else:
            record["blob_id"] = None
        return record

    def _store_eligible_blobs(self, changes: list[dict[str, Any]]) -> None:
        """Persist eligible changed content once, by content hash."""
        if self._workspace_dir is None:
            return
        for change in changes:
            if change["status"] == "deleted":
                continue
            blob_id = (change.get("after") or {}).get("blob_id")
            if not blob_id or blob_id in self._blobs:
                continue
            full = self._workspace_dir / change["path"]
            try:
                descriptor = os.open(full, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, "rb") as handle:
                    if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                        raise OSError("artifact is not a regular file")
                    content = handle.read(_CONTENT_LIMIT + 1)
                if (
                    len(content) > _CONTENT_LIMIT
                    or len(content) != change["after"]["size"]
                    or _sha256_bytes(content) != blob_id
                ):
                    change["after"]["blob_id"] = None
                    continue
                self._blobs[blob_id] = content
            except OSError:
                change["after"]["blob_id"] = None

    def _build_revision(
        self, changes: list[dict[str, Any]], provenance: dict[str, Any]
    ) -> dict[str, Any]:
        """Build one content-addressed revision event."""
        parent = self._revisions[-1]["revision_id"] if self._revisions else None
        tree_hash = _sha256_text(
            json.dumps(self._scan_workspace(), sort_keys=True, default=str)
        )
        payload = {
            "parent": parent,
            "provenance": provenance,
            "tree_hash": tree_hash,
            "changes": changes,
        }
        revision_id = "rev-" + _sha256_text(
            json.dumps(payload, sort_keys=True, default=str)
        )
        return {
            "revision_id": revision_id,
            "sequence": len(self._revisions) + 1,
            **payload,
        }

    def _persist_revision(self, revision: dict[str, Any]) -> None:
        """Append one revision event and its blobs to session storage."""
        if self._root is None:
            return
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            blob_dir = self._root / "blobs"
            for change in revision["changes"]:
                blob_id = (change.get("after") or {}).get("blob_id")
                if not blob_id:
                    continue
                blob_dir.mkdir(parents=True, exist_ok=True)
                (blob_dir / blob_id).write_bytes(self._blobs[blob_id])
            with (self._root / "revisions.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(revision, sort_keys=True, default=str) + "\n")
        except OSError as exc:
            self._mark_incomplete(
                f"failed to persist revision {revision['revision_id']}: {exc}"
            )
