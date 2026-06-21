"""Session workspace binding helpers for native tools.

Milestone 5 hardening: the workspace ContextVar MUST be bound before any
tool call. If unset, ``resolve_workspace_path`` raises
``WorkspaceNotBoundError`` instead of silently falling back to the process
cwd (which caused the experiment-4 path-mismatch failures).
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path


_WORKSPACE_DIR: ContextVar[Path | None] = ContextVar("native_workspace_dir", default=None)


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
        return
    workspace = Path(workspace_dir).expanduser().resolve()
    # ponytail: directory creation belongs to the CLI layer, not the tool
    # binding. Silently recreating a deleted workspace masks bugs.
    _WORKSPACE_DIR.set(workspace)


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

    # Re-root absolute paths that look like workspace subpaths.
    # E.g. /backend/api/auth.py → /workspace/experiment-4/backend/api/auth.py
    # if the latter exists. This fixes the experiment-4 mismatch.
    if candidate.is_absolute():
        # Try re-rooting under the workspace first.
        rerooted = (workspace / candidate.relative_to(candidate.anchor)).resolve(strict=False)
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
        p = Path(path).resolve(strict=False)
        return str(p.relative_to(workspace))
    except (ValueError, RuntimeError):
        return str(path)


def bind_workspace_to_tool(tool: object) -> None:
    """Attach the common workspace binder to an SDK Tool instance."""
    setattr(tool, "bind_workspace", bind_workspace)
