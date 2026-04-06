"""Context file discovery with priority-based loading."""

from pathlib import Path


CONTEXT_FILE_NAMES = [".hermes.md", "AGENTS.md", "CLAUDE.md"]


class ContextDiscoveryError(Exception):
    """Raised when context discovery fails."""

    pass


class ContextLoadError(Exception):
    """Raised when context file cannot be loaded."""

    pass


class ContextDiscovery:
    """Discovers and loads context files.

    Searches for context files in priority order:
    .hermes.md (highest) > AGENTS.md > CLAUDE.md

    Searches current directory and parent directories up to max_depth.
    """

    # Directories to skip during traversal
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox"}

    def __init__(
        self,
        root_dir: Path | None = None,
        max_depth: int = 5,
        follow_symlinks: bool = False,
    ):
        """Initialize with optional root directory.

        Args:
            root_dir: Starting directory for discovery (defaults to cwd)
            max_depth: Maximum parent directory depth to traverse
            follow_symlinks: Whether to follow symbolic links
        """
        self.root_dir = root_dir or Path.cwd()
        self.max_depth = max_depth
        self.follow_symlinks = follow_symlinks

    def discover(self) -> list[tuple[Path, int]]:
        """Discover context files with priority.

        Priority order: .hermes.md (highest) > AGENTS.md > CLAUDE.md

        Returns:
            List of (file_path, priority) tuples

        Raises:
            ContextDiscoveryError: If discovery fails
        """
        found_files: list[tuple[Path, int]] = []

        # Start from root and traverse up
        current_dir = self.root_dir.resolve()
        depth = 0

        while depth <= self.max_depth:
            if not current_dir.exists():
                break

            # Check for context files in current directory
            for filename in CONTEXT_FILE_NAMES:
                file_path = current_dir / filename

                if file_path.exists() and file_path.is_file():
                    # Check if we should follow symlinks
                    if file_path.is_symlink() and not self.follow_symlinks:
                        continue

                    # Calculate priority (lower = higher priority)
                    priority = CONTEXT_FILE_NAMES.index(filename)
                    found_files.append((file_path, priority))

            # Move to parent directory
            parent = current_dir.parent
            if parent == current_dir:
                # Reached filesystem root
                break
            current_dir = parent
            depth += 1

        # Sort by priority (lower = higher priority)
        found_files.sort(key=lambda x: x[1])

        return found_files

    def load_contexts(self) -> list[str]:
        """Load all discovered context files.

        Returns:
            List of context contents in priority order

        Raises:
            ContextLoadError: If file cannot be read
        """
        discovered = self.discover()
        contents = []

        for file_path, _ in discovered:
            try:
                content = file_path.read_text(encoding="utf-8")
                contents.append(content)
            except OSError as e:
                raise ContextLoadError(f"Failed to read {file_path}: {e}")

        return contents

    def merge_contexts(self) -> str:
        """Merge all discovered contexts into single string.

        Returns:
            Merged context string

        Raises:
            ContextLoadError: If file cannot be read
        """
        contents = self.load_contexts()
        return "\n\n---\n\n".join(contents)
