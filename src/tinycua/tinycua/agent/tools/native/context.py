"""Session workspace binding helpers for native tools.

Milestone 5 hardening: the workspace ContextVar MUST be bound before any
tool call. If unset, ``resolve_workspace_path`` raises
``WorkspaceNotBoundError`` instead of silently falling back to the process
cwd (which caused the experiment-4 path-mismatch failures).
"""

from __future__ import annotations

import hashlib
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path


_WORKSPACE_DIR: ContextVar[Path | None] = ContextVar(
    "native_workspace_dir", default=None
)
_MANAGED_DRAFT_DIR: ContextVar[Path | None] = ContextVar(
    "native_managed_draft_dir", default=None
)


@dataclass
class _FileRevision:
    """Read authorization for one exact file revision."""

    sha256: str
    total_lines: int
    ranges: list[tuple[int, int]] = field(default_factory=list)
    complete: bool = False


@dataclass
class _FileLedger:
    """Execution-scoped file read authorizations."""

    workspace: Path
    execution_id: str
    revisions: dict[Path, _FileRevision] = field(default_factory=dict)


_FILE_LEDGER: ContextVar[_FileLedger | None] = ContextVar(
    "native_file_ledger", default=None
)


class WorkspaceNotBoundError(RuntimeError):
    """Raised when a tool resolves a path but the workspace is not bound."""

    def __init__(self) -> None:
        super().__init__(
            "Workspace not bound — call bind_workspace() before using file/shell tools. "
            "The workspace ContextVar must be set to the canonical workspace root."
        )


def bind_workspace(workspace_dir: str | Path | None) -> None:
    """Bind native tools in the current context to a workspace directory.

    Args:
        workspace_dir: Workspace root, or ``None`` to unbind (tools will
            then raise WorkspaceNotBoundError on path resolution).
    """
    if workspace_dir is None:
        _WORKSPACE_DIR.set(None)
        _MANAGED_DRAFT_DIR.set(None)
        _FILE_LEDGER.set(None)
        return
    workspace = Path(workspace_dir).expanduser().resolve()
    # ponytail: directory creation belongs to the CLI layer, not the tool
    # binding. Silently recreating a deleted workspace masks bugs.
    _WORKSPACE_DIR.set(workspace)
    _MANAGED_DRAFT_DIR.set(None)
    ledger = _FILE_LEDGER.get()
    if ledger is not None and ledger.workspace != workspace:
        _FILE_LEDGER.set(None)


def get_workspace_dir() -> Path | None:
    """Return the currently bound workspace, if any."""
    return _WORKSPACE_DIR.get()


def resolve_workspace_path(path: str) -> Path:
    """Resolve a tool path under the bound workspace.

    The workspace MUST be bound. If unset, raises ``WorkspaceNotBoundError``
    (no silent cwd fallback — this caused the experiment-4 path mismatch
    where the reviewer checked ``/backend/...`` instead of
    ``/workspace/experiment-4/backend/...``).

    Absolute paths that match a workspace subpath are re-rooted under the
    workspace (heuristic: if ``workspace / path`` exists, prefer it).

    FR-035: absolute paths already under the workspace are normalized by
    stripping repeated workspace prefixes. The model sometimes echoes back
    a path that already contains the workspace prefix, or contains it twice
    (``/ws/exp-2/ws/exp-2/report.md``). The doubled path is stripped to the
    canonical form so ``write_file``/``append_file`` don't create a nested
    duplicate and ``str_replace`` finds the correct file.

    Args:
        path: User-supplied path (relative or absolute).

    Returns:
        Absolute resolved path under the workspace.

    Raises:
        WorkspaceNotBoundError: If the workspace is not bound.
        ValueError: If the resolved path escapes the workspace.
    """
    workspace = get_workspace_dir()
    if workspace is None:
        raise WorkspaceNotBoundError

    candidate = Path(path).expanduser()

    # FR-035: normalize absolute paths that are already under the workspace.
    # Strip repeated workspace prefixes (the doubled-path case) so the
    # canonical path is always returned, even if the doubled file exists.
    if candidate.is_absolute():
        resolved_abs = candidate.resolve(strict=False)
        if resolved_abs.is_relative_to(workspace):
            rel = resolved_abs.relative_to(workspace)
            rel_parts = rel.parts
            # ws_tail = the workspace's full path after root (e.g.
            # ('workspace', 'experiment-2') for /workspace/experiment-2).
            # The doubled-path case: the model echoes back the full workspace
            # path it saw in a tool result, producing
            # /ws/exp-2/ws/exp-2/report.md. Strip the workspace's own
            # segments from the front of the relative part.
            ws_tail = workspace.parts[1:]
            while (
                len(rel_parts) > len(ws_tail) and rel_parts[: len(ws_tail)] == ws_tail
            ):
                rel_parts = rel_parts[len(ws_tail) :]
            if len(rel_parts) < len(rel.parts):
                # A workspace prefix was stripped — re-resolve the remainder.
                resolved = (workspace / Path(*rel_parts)).resolve(strict=False)
            else:
                resolved = resolved_abs
        else:
            # Not under workspace — try re-rooting under the workspace first.
            # E.g. /backend/api/auth.py → /workspace/experiment-4/backend/api/auth.py
            # if the latter exists. This fixes the experiment-4 mismatch.
            rerooted = (workspace / candidate.relative_to(candidate.anchor)).resolve(
                strict=False
            )
            if rerooted.exists():
                candidate = rerooted
            resolved = candidate.resolve(strict=False)
    else:
        resolved = (workspace / candidate).resolve(strict=False)

    if resolved != workspace and not resolved.is_relative_to(workspace):
        msg = f"Path outside workspace ({workspace}): {path}. Use a relative path instead."
        raise ValueError(msg)
    return resolved


def to_workspace_relative(path: str | Path) -> str:
    """Convert an absolute path to a workspace-relative string.

    If the path is under the workspace, returns the relative form (e.g.
    ``backend/api/auth.py``). Otherwise returns the path as-is.

    Args:
        path: An absolute or relative path.

    Returns:
        The workspace-relative path string, or the original if not under
        the workspace.
    """
    workspace = get_workspace_dir()
    if workspace is None:
        return str(path)
    try:
        resolved = Path(path).resolve(strict=False)
        return str(resolved.relative_to(workspace))
    except (ValueError, RuntimeError):
        return str(path)


def bind_managed_draft_dir(draft_dir: str | Path | None) -> None:
    """Authorize native file tools to access one node execution's draft directory."""
    _MANAGED_DRAFT_DIR.set(Path(draft_dir).resolve() if draft_dir else None)


def bind_file_execution(execution_id: str | None) -> None:
    """Bind file-read authorization to one node execution.

    A different execution ID starts with an empty ledger. Rebinding the same
    ID in the same workspace preserves its successful reads.
    """
    workspace = get_workspace_dir()
    normalized_id = str(execution_id or "")
    if workspace is None or not normalized_id:
        _FILE_LEDGER.set(None)
        return
    ledger = _FILE_LEDGER.get()
    if (
        ledger is None
        or ledger.workspace != workspace
        or ledger.execution_id != normalized_id
    ):
        _FILE_LEDGER.set(_FileLedger(workspace=workspace, execution_id=normalized_id))


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _merged_ranges(
    ranges: list[tuple[int, int]], new_range: tuple[int, int]
) -> list[tuple[int, int]]:
    """Merge one inclusive line range into sorted, non-overlapping ranges."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted([*ranges, new_range]):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def record_file_read(
    path: Path,
    content: bytes,
    total_lines: int,
    start: int | None = None,
    end: int | None = None,
    complete: bool = False,
) -> None:
    """Record successful coverage for one canonical file revision."""
    ledger = _FILE_LEDGER.get()
    if ledger is None:
        return
    digest = _sha256(content)
    revision = ledger.revisions.get(path)
    if (
        revision is None
        or revision.sha256 != digest
        or revision.total_lines != total_lines
    ):
        revision = _FileRevision(digest, total_lines)
        ledger.revisions[path] = revision
    if complete:
        revision.complete = True
        revision.ranges = [(1, total_lines)] if total_lines else []
        return
    if start is None or end is None or start > end:
        return
    revision.ranges = _merged_ranges(revision.ranges, (start, end))
    revision.complete = total_lines <= 0 or (
        bool(revision.ranges)
        and revision.ranges[0][0] <= 1
        and revision.ranges[-1][1] >= total_lines
        and all(
            previous[1] + 1 >= current[0]
            for previous, current in zip(revision.ranges, revision.ranges[1:])
        )
    )


def record_file_result(path: Path, content: bytes, total_lines: int) -> None:
    """Record a successful mutation result as fully observed."""
    record_file_read(path, content, total_lines, complete=True)


def authorize_file_mutation(path: Path) -> tuple[bytes | None, str | None]:
    """Return current bytes when this execution may mutate ``path``."""
    try:
        content = path.read_bytes()
    except PermissionError:
        return None, f"Permission denied: {path}"
    except OSError as exc:
        return None, f"Failed to read current file revision: {exc}"

    ledger = _FILE_LEDGER.get()
    revision = ledger.revisions.get(path) if ledger is not None else None
    if revision is None:
        return (
            None,
            "Read the complete current file revision with this node execution "
            "before mutating it.",
        )
    digest = _sha256(content)
    if digest != revision.sha256:
        ledger.revisions.pop(path, None)
        return (
            None,
            "File changed since it was read; read the current revision before "
            "mutating it.",
        )
    if not revision.complete:
        return (
            None,
            "Read the complete current file revision with this node execution "
            "before mutating it.",
        )
    return content, None


def is_hidden_workspace_path(path: Path) -> bool:
    """Return whether an internal draft path is unavailable to this node."""
    workspace = get_workspace_dir()
    if workspace is None:
        return False
    drafts_root = workspace / ".tinycua"
    if not path.is_relative_to(drafts_root):
        return False
    draft_dir = _MANAGED_DRAFT_DIR.get()
    return draft_dir is None or not path.is_relative_to(draft_dir)


def bind_workspace_to_tool(tool: object) -> None:
    """Attach the common workspace binder to an SDK Tool instance."""
    setattr(tool, "bind_workspace", bind_workspace)
    setattr(tool, "bind_managed_draft_dir", bind_managed_draft_dir)


def bind_file_execution_to_tool(tool: object) -> None:
    """Attach the execution-scoped file ledger binder to an SDK Tool."""
    setattr(tool, "bind_file_execution", bind_file_execution)
