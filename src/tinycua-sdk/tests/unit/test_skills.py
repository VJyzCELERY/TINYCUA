"""Tests for skills module."""

import pytest
from unittest.mock import MagicMock
from tinycua_sdk.skills.loader import SkillLoader, SkillNotFoundError, SkillParseError
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.cache import SkillCache
from tinycua_sdk.skills.models import Skill


class TestSkillLoader:
    """Tests for SkillLoader."""

    def test_skill_loader_init(self):
        """SkillLoader initializes."""
        loader = SkillLoader()
        assert loader is not None


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_registry_init(self):
        """SkillRegistry initializes."""
        registry = SkillRegistry()
        assert registry is not None


class TestSkillCache:
    """Tests for SkillCache."""

    def test_cache_init(self):
        """SkillCache initializes."""
        cache = SkillCache()
        assert cache is not None
