"""Skills cache with LRU eviction."""

import threading

from tinycua_sdk.skills.models import Skill


class SkillCache:
    """LRU in-memory cache for skills.

    Provides fast skill access with thread-safe operations.
    Ephemeral only — no disk persistence.
    """

    def __init__(self, max_size: int = 100):
        """Initialize the cache.

        Args:
            max_size: Maximum number of skills in LRU cache.
        """
        self.max_size = max_size

        self._cache: dict[str, Skill] = {}
        self._access_order: list[str] = []
        self._lock = threading.RLock()

    def get(self, key: str) -> Skill | None:
        """Get skill from cache.

        Args:
            key: Skill name.

        Returns:
            Cached Skill or None.
        """
        with self._lock:
            skill = self._cache.get(key)

            if skill is not None:
                # Update access order for LRU
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)

            return skill

    def put(self, key: str, skill: Skill) -> None:
        """Put skill in cache.

        Args:
            key: Skill name.
            skill: Skill to cache.
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
            skill_name: Name of skill to invalidate.
        """
        with self._lock:
            if skill_name in self._cache:
                del self._cache[skill_name]
            if skill_name in self._access_order:
                self._access_order.remove(skill_name)

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
