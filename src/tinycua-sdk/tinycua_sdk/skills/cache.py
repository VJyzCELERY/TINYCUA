"""Skills cache with LRU and disk snapshot."""

import json
import threading
from pathlib import Path
from datetime import datetime

from tinycua_sdk.skills.models import Skill


class SkillCache:
    """Two-layer cache: LRU in-memory + disk snapshot.

    Provides fast skill access with persistence across sessions.
    Thread-safe implementation using RLock for concurrent access.
    """

    def __init__(
        self,
        max_size: int = 100,
        snapshot_dir: Path | None = None,
        check_modification: bool = True,
    ):
        """Initialize the cache.

        Args:
            max_size: Maximum number of skills in LRU cache
            snapshot_dir: Directory for disk snapshots
            check_modification: Whether to check file modification times
        """
        self.max_size = max_size
        self.snapshot_dir = (
            snapshot_dir or Path.home() / ".tinycua" / "cache" / "skills"
        )
        self.check_modification = check_modification

        self._cache: dict[str, Skill] = {}
        self._access_order: list[str] = []
        self._lock = threading.RLock()

    def get(self, key: str) -> Skill | None:
        """Get skill from cache.

        Args:
            key: Skill name

        Returns:
            Cached Skill or None
        """
        with self._lock:
            skill = self._cache.get(key)

            if skill is not None:
                # Check if stale if modification checking enabled
                if self.check_modification and self.invalidate_if_stale(skill):
                    self.invalidate(key)
                    return None

                # Update access order for LRU
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)

            return skill

    def put(self, key: str, skill: Skill) -> None:
        """Put skill in cache.

        Args:
            key: Skill name
            skill: Skill to cache
        """
        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            self._cache[key] = skill

            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def invalidate(self, skill_name: str) -> None:
        """Invalidate a specific skill from cache.

        Args:
            skill_name: Name of skill to invalidate
        """
        with self._lock:
            if skill_name in self._cache:
                del self._cache[skill_name]
            if skill_name in self._access_order:
                self._access_order.remove(skill_name)

    def invalidate_if_stale(self, skill: Skill) -> bool:
        """Check if skill is stale based on file modification time.

        Args:
            skill: Skill to check

        Returns:
            True if skill is stale and should be reloaded
        """
        if skill.path is None:
            return False

        skill_md_path = skill.path / "SKILL.md"
        if not skill_md_path.exists():
            return True

        current_mtime = skill_md_path.stat().st_mtime
        skill_mtime = skill.modified_at.timestamp() if skill.modified_at else 0

        return current_mtime > skill_mtime

    def save_snapshot(self) -> None:
        """Save cache snapshot to disk."""
        with self._lock:
            if not self._cache:
                return

            self.snapshot_dir.mkdir(parents=True, exist_ok=True)

            snapshot = {
                "saved_at": datetime.now().isoformat(),
                "skills": {},
            }

            for key, skill in self._cache.items():
                skill_data = skill.to_dict()
                skill_data["_cached_mtime"] = (
                    skill.modified_at.timestamp() if skill.modified_at else 0
                )
                skill_data["_cached_ctime"] = (
                    skill.created_at.timestamp() if skill.created_at else 0
                )
                snapshot["skills"][key] = skill_data

            snapshot_path = self.snapshot_dir / "skills_snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    def load_snapshot(self) -> None:
        """Load cache snapshot from disk."""
        with self._lock:
            snapshot_path = self.snapshot_dir / "skills_snapshot.json"

            if not snapshot_path.exists():
                return

            try:
                content = snapshot_path.read_text(encoding="utf-8")
                snapshot = json.loads(content)

                for key, skill_data in snapshot.get("skills", {}).items():
                    # Reconstruct Skill from dict
                    skill = Skill(
                        name=skill_data.get("name", key),
                        description=skill_data.get("description", ""),
                        category=skill_data.get("category", "general"),
                        instructions=skill_data.get("instructions", ""),
                        tools=skill_data.get("tools", []),
                        dependencies=skill_data.get("dependencies", []),
                        path=Path(skill_data["path"])
                        if skill_data.get("path")
                        else None,
                        metadata=skill_data.get("metadata", {}),
                    )

                    # Restore modification time
                    cached_mtime = skill_data.get("_cached_mtime", 0)
                    if cached_mtime:
                        skill.modified_at = datetime.fromtimestamp(cached_mtime)

                    # Restore creation time
                    cached_ctime = skill_data.get("_cached_ctime", 0)
                    if cached_ctime:
                        skill.created_at = datetime.fromtimestamp(cached_ctime)

                    self._cache[key] = skill
                    self._access_order.append(key)

            except (json.JSONDecodeError, KeyError, ValueError):
                # Invalid snapshot, ignore
                pass

    def clear(self) -> None:
        """Clear all cached skills."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def _evict_lru(self) -> None:
        """Evict the least recently used skill."""
        if self._access_order:
            lru_key = self._access_order.pop(0)
            if lru_key in self._cache:
                del self._cache[lru_key]

    @property
    def size(self) -> int:
        """Get the current cache size."""
        with self._lock:
            return len(self._cache)
