"""Session workspace binding helpers for native tools.

Milestone 5 hardening: the workspace ContextVar MUST be bound before any
tool call. If unset, ``resolve_workspace_path`` raises
``WorkspaceNotBoundError`` instead of silently falling back to the process
cwd (which caused the experiment-4 path-mismatch failures).
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path


_WORKSPACE_DIR: ContextVar[Path | None] = ContextVar(
    "native_workspace_dir", default=None
)
_MANAGED_DRAFT_DIR: ContextVar[Path | None] = ContextVar(
    "native_managed_draft_dir", default=None
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
        return
    workspace = Path(workspace_dir).expanduser().resolve()
    # ponytail: directory creation belongs to the CLI layer, not the tool
    # binding. Silently recreating a deleted workspace masks bugs.
    _WORKSPACE_DIR.set(workspace)
    _MANAGED_DRAFT_DIR.set(None)


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
