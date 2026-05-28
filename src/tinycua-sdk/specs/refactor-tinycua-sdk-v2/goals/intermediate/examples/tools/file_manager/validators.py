"""Path validators for the file_manager tool."""

from pathlib import Path


class PathValidationError(ValueError):
    """Raised when a path fails validation."""


def validate_path(raw_path: str) -> Path:
    """Validate and resolve a path.

    Rules:
      - Must not contain '..' that escapes the project root.
      - Must be relative or within the allowed base directory.
    """
    path = Path(raw_path).expanduser().resolve()

    # Prevent traversal outside the working directory
    cwd = Path.cwd().resolve()
    try:
        path.relative_to(cwd)
    except ValueError:
        raise PathValidationError(
            f"Path '{raw_path}' is outside the allowed directory: {cwd}"
        )

    return path
