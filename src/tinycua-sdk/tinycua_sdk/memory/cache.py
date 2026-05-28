"""Prompt caching with TTL and size limits for OpenAI-compatible endpoints."""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached prompt entry."""

    key: str
    value: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl: float | None = None
    hit_count: int = 0


class PromptCache:
    """Prompt caching with TTL and size limits."""

    def __init__(
        self,
        max_size: int = 100,
        default_ttl: float | None = 3600,
        refresh_strategy: str = "lru",
    ):
        """Initialize prompt cache.

        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live in seconds (None for no expiration)
            refresh_strategy: Cache refresh strategy ('lru', 'lfu', 'ttl')

        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._refresh_strategy = refresh_strategy
        self._cache: dict[str, CacheEntry] = {}
        self._lock = RLock()

    def get(self, prompt: str) -> str | None:
        """Get cached prompt result.

        Args:
            prompt: Prompt to look up

        Returns:
            Cached result or None if not found/invalid

        """
        with self._lock:
            key = self._make_key(prompt)
            entry = self._cache.get(key)

            if entry is None:
                return None

            if self._is_expired(entry):
                del self._cache[key]
                return None

            entry.hit_count += 1
            entry.last_accessed = time.time()
            return entry.value

    def set(self, prompt: str, result: str, ttl: float | None = None) -> dict[str, Any]:
        """Cache a prompt result.

        Args:
            prompt: Prompt to cache
            result: Result to cache
            ttl: Optional TTL override

        Returns:
            Result dictionary

        """
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            key = self._make_key(prompt)
            entry = CacheEntry(
                key=key,
                value=result,
                ttl=ttl or self._default_ttl,
            )
            self._cache[key] = entry
            return {"success": True, "key": key}

    def invalidate(self, prompt: str) -> dict[str, Any]:
        """Invalidate a cached entry.

        Args:
            prompt: Prompt to invalidate

        Returns:
            Result dictionary

        """
        with self._lock:
            key = self._make_key(prompt)
            if key in self._cache:
                del self._cache[key]
                return {"success": True, "key": key}
            return {"success": False, "key": key, "error": "Not found"}

    def clear(self) -> dict[str, Any]:
        """Clear all cached entries.

        Returns:
            Result dictionary

        """
        with self._lock:
            self._cache.clear()
            return {"success": True}

    def _make_key(self, prompt: str) -> str:
        """Generate cache key using SHA256.

        Args:
            prompt: Prompt to hash

        Returns:
            Cache key

        """
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry is expired.

        Args:
            entry: Cache entry to check

        Returns:
            True if expired

        """
        if entry.ttl is None:
            return False
        return time.time() - entry.created_at > entry.ttl

    def _evict_oldest(self) -> None:
        """Evict oldest entry based on refresh strategy."""
        if not self._cache:
            return

        if self._refresh_strategy == "lru":
            oldest = min(self._cache.values(), key=lambda e: e.last_accessed)
            del self._cache[oldest.key]
        elif self._refresh_strategy == "lfu":
            least_used = min(self._cache.values(), key=lambda e: e.hit_count)
            del self._cache[least_used.key]
        elif self._refresh_strategy == "ttl":
            expired = [e for e in self._cache.values() if self._is_expired(e)]
            if expired:
                del self._cache[expired[0].key]
            else:
                oldest = min(self._cache.values(), key=lambda e: e.created_at)
                del self._cache[oldest.key]
        else:
            oldest = min(self._cache.values(), key=lambda e: e.created_at)
            del self._cache[oldest.key]

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary

        """
        with self._lock:
            total_hits = sum(e.hit_count for e in self._cache.values())
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "total_hits": total_hits,
                "default_ttl": self._default_ttl,
            }


__all__ = ["CacheEntry", "PromptCache"]
