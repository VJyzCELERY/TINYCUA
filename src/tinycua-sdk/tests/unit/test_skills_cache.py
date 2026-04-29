# Unit tests for Skills Cache

from tinycua_sdk.skills.cache import SkillCache
from tinycua_sdk.skills.models import Skill


class TestSkillCache:
    """Tests for the SkillCache class."""

    def test_put_and_get(self):
        """Test basic put and get operations."""
        cache = SkillCache()
        skill = Skill(name="Test Skill", description="Test")

        cache.put("test", skill)
        result = cache.get("test")

        assert result is not None
        assert result.name == "Test Skill"

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = SkillCache()

        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = SkillCache(max_size=2)

        cache.put("a", Skill(name="A"))
        cache.put("b", Skill(name="B"))
        cache.put("c", Skill(name="C"))  # Should evict "a"

        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_invalidate(self):
        """Test manual cache invalidation."""
        cache = SkillCache()

        cache.put("test", Skill(name="Test"))
        cache.invalidate("test")

        assert cache.get("test") is None

    def test_clear(self):
        """Test clearing the cache."""
        cache = SkillCache()

        cache.put("a", Skill(name="A"))
        cache.put("b", Skill(name="B"))
        cache.clear()

        assert cache.size == 0

    def test_access_order_tracking(self):
        """Test that access order is tracked for LRU."""
        cache = SkillCache(max_size=3)

        cache.put("a", Skill(name="A"))
        cache.put("b", Skill(name="B"))
        cache.put("c", Skill(name="C"))

        # Access "a" to make it most recent
        cache.get("a")

        # Add new item - should evict "b" (least recent after "a" was accessed)
        cache.put("d", Skill(name="D"))

        assert cache.get("a") is not None  # Just accessed
        assert cache.get("b") is None  # Evicted
        assert cache.get("c") is not None
        assert cache.get("d") is not None
