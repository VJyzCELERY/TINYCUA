"""Session workspace binding helpers for native tools."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path


_WORKSPACE_DIR: ContextVar[Path | None] = ContextVar("native_workspace_dir", default=None)


def bind_workspace(workspace_dir: str | Path | None) -> None:
    """Bind native tools in the current context to a workspace directory.

    Args:
        workspace_dir: Workspace root, or ``None`` to restore legacy cwd behavior.
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
    """Resolve a tool path under the bound workspace when configured.

    Without a bound workspace this preserves the legacy behavior: absolute
    paths are used as-is and relative paths are resolved from process cwd.

    Args:
        path: User-supplied path.

    Returns:
        Absolute resolved path.

    Raises:
        ValueError: If a bound workspace is configured and the resolved path
            escapes it.
    """
    workspace = get_workspace_dir()
    candidate = Path(path).expanduser()
    if workspace is None:
        return candidate if candidate.is_absolute() else Path.cwd() / candidate

    resolved = (
        candidate.resolve(strict=False)
        if candidate.is_absolute()
        else (workspace / candidate).resolve(strict=False)
    )
    if resolved != workspace and not resolved.is_relative_to(workspace):
        msg = f"Path outside workspace: {path}"
        raise ValueError(msg)
    return resolved


def bind_workspace_to_tool(tool: object) -> None:
    """Attach the common workspace binder to an SDK Tool instance."""
    setattr(tool, "bind_workspace", bind_workspace)
