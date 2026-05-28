"""Permission checks for the file_manager tool."""

from pathlib import Path


class AccessDeniedError(PermissionError):
    """Raised when a read/write operation is not allowed."""


# Block-list of sensitive paths (relative to project root)
_BLOCKED_PATTERNS = [
    ".env",
    ".git",
    "secrets",
    "private_key",
]


def check_access(path: Path, mode: str = "read") -> None:
    """Check whether the given path is accessible for the requested mode.

    Args:
        path: Resolved Path object.
        mode: "read" or "write".

    Raises:
        AccessDeniedError: If the path is blocked.
    """
    name_lower = path.name.lower()
    for blocked in _BLOCKED_PATTERNS:
        if blocked in name_lower:
            raise AccessDeniedError(
                f"Access denied: '{path.name}' matches blocked pattern '{blocked}'"
            )

    if mode == "write" and path.suffix in (".key", ".pem", ".p12"):
        raise AccessDeniedError(
            f"Writing to key files is not allowed: {path}"
        )
