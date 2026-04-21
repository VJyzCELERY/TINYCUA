import pytest
import threading
import time
from tinycua_sdk.memory.cache import CacheEntry, PromptCache


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_creation(self):
        """Test creating cache entry."""
        entry = CacheEntry(key="test", value="result")
        assert entry.key == "test"
        assert entry.value == "result"
        assert entry.hit_count == 0


class TestPromptCache:
    """Test PromptCache class."""

    def test_initialization(self):
        """Test initializing cache."""
        cache = PromptCache(max_size=10, default_ttl=60)
        assert cache._max_size == 10
        assert cache._default_ttl == 60

    def test_set_and_get(self):
        """Test setting and getting cache entries."""
        cache = PromptCache()
        cache.set("prompt 1", "result 1")
        result = cache.get("prompt 1")
        assert result == "result 1"

    def test_get_nonexistent(self):
        """Test getting non-existent entry returns None."""
        cache = PromptCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_invalidation(self):
        """Test invalidating cache entries."""
        cache = PromptCache()
        cache.set("prompt 1", "result 1")
        cache.invalidate("prompt 1")
        result = cache.get("prompt 1")
        assert result is None

    def test_clear_cache(self):
        """Test clearing all cache entries."""
        cache = PromptCache()
        cache.set("prompt 1", "result 1")
        cache.set("prompt 2", "result 2")
        cache.clear()
        assert cache.get("prompt 1") is None
        assert cache.get("prompt 2") is None

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = PromptCache(default_ttl=1)
        cache.set("prompt 1", "result 1")
        time.sleep(1.1)
        result = cache.get("prompt 1")
        assert result is None

    def test_custom_ttl(self):
        """Test custom TTL."""
        cache = PromptCache(default_ttl=10)
        cache.set("prompt 1", "result 1", ttl=1)
        time.sleep(1.1)
        result = cache.get("prompt 1")
        assert result is None

    def test_cache_size_limit(self):
        """Test cache size limit triggers eviction."""
        cache = PromptCache(max_size=2)
        cache.set("prompt 1", "result 1")
        cache.set("prompt 2", "result 2")
        cache.set("prompt 3", "result 3")
        assert cache.get("prompt 1") is None
        assert cache.get("prompt 2") == "result 2"
        assert cache.get("prompt 3") == "result 3"

    def test_key_generation(self):
        """Test SHA256 key generation."""
        cache = PromptCache()
        key1 = cache._make_key("test prompt")
        key2 = cache._make_key("test prompt")
        assert key1 == key2
        assert len(key1) == 64

    def test_stats(self):
        """Test cache statistics."""
        cache = PromptCache()
        cache.set("prompt 1", "result 1")
        cache.get("prompt 1")
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["total_hits"] == 1


class TestPromptCacheRefreshStrategies:
    """Test different refresh strategies."""

    def test_lru_strategy(self):
        """Test LRU eviction strategy."""
        cache = PromptCache(max_size=2, refresh_strategy="lru")
        cache.set("prompt 1", "result 1")
        time.sleep(0.1)
        cache.set("prompt 2", "result 2")
        cache.get("prompt 1")
        cache.set("prompt 3", "result 3")
        assert cache.get("prompt 1") is not None
        assert cache.get("prompt 2") is None

    def test_lfu_strategy(self):
        """Test LFU eviction strategy."""
        cache = PromptCache(max_size=2, refresh_strategy="lfu")
        cache.set("prompt 1", "result 1")
        cache.set("prompt 2", "result 2")
        cache.get("prompt 1")
        cache.get("prompt 1")
        cache.set("prompt 3", "result 3")
        assert cache.get("prompt 2") is None


class TestPromptCacheThreadSafety:
    """Test thread safety of PromptCache."""

    def test_concurrent_set_get(self):
        """Test concurrent set and get operations."""
        cache = PromptCache()
        errors = []

        def writer():
            try:
                for i in range(50):
                    cache.set(f"prompt {i}", f"result {i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(50):
                    _ = cache.get(f"prompt {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(2)]
        threads += [threading.Thread(target=reader) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0