"""Tests for skills module."""

import pytest
from pathlib import Path
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

    def test_discover_skills_empty_directory(self, tmp_path):
        """discover_skills returns empty list for empty directory."""
        loader = SkillLoader()
        skills = loader.discover_skills(tmp_path)
        assert skills == []

    def test_discover_skills_nonexistent_directory(self):
        """discover_skills returns empty list for nonexistent directory."""
        loader = SkillLoader()
        skills = loader.discover_skills(Path("/nonexistent/path"))
        assert skills == []

    def test_discover_skills_with_valid_skills(self, tmp_path):
        """discover_skills finds skills in valid directories."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: test_skill\ndescription: A test skill\ncategory: testing\n---\n# Instructions\nTest instructions."
        )

        loader = SkillLoader()
        skills = loader.discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].name == "test_skill"
        assert skills[0].category == "testing"

    def test_discover_skills_skips_invalid_directories(self, tmp_path):
        """discover_skills skips directories without SKILL.md."""
        valid_skill = tmp_path / "valid_skill"
        valid_skill.mkdir()
        (valid_skill / "SKILL.md").write_text(
            "---\nname: valid\ndescription: Valid skill\n---\n# Instructions\nTest."
        )

        invalid_skill = tmp_path / "invalid_skill"
        invalid_skill.mkdir()

        loader = SkillLoader()
        skills = loader.discover_skills(tmp_path)
        assert len(skills) == 1
        assert skills[0].name == "valid"

    def test_load_skill_success(self, tmp_path):
        """load_skill loads a valid skill."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: my_skill\ndescription: My skill description\ncategory: tools\ntools:\n  - tool1\n  - tool2\n---\n# Instructions\nUse this skill to do things."
        )

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.name == "my_skill"
        assert skill.description == "My skill description"
        assert skill.category == "tools"
        assert skill.tools == ["tool1", "tool2"]

    def test_load_skill_not_found(self, tmp_path):
        """load_skill raises SkillNotFoundError when SKILL.md missing."""
        skill_dir = tmp_path / "missing_skill"
        skill_dir.mkdir()

        loader = SkillLoader()
        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load_skill(skill_dir)
        assert "SKILL.md not found" in str(exc_info.value)

    def test_load_skill_invalid_yaml(self, tmp_path):
        """load_skill raises SkillParseError for invalid YAML."""
        skill_dir = tmp_path / "bad_yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test\ninvalid: [yaml: broken\n---\n# Instructions\nTest."
        )

        loader = SkillLoader()
        with pytest.raises(SkillParseError):
            loader.load_skill(skill_dir)

    def test_load_skill_no_frontmatter(self, tmp_path):
        """load_skill works without YAML frontmatter."""
        skill_dir = tmp_path / "no_yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# Instructions\nJust plain markdown instructions."
        )

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)
        assert skill.name == "no_yaml"
        assert skill.description == ""


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_registry_init(self):
        """SkillRegistry initializes."""
        registry = SkillRegistry()
        assert registry is not None

    def test_registry_register_and_get(self, tmp_path):
        """SkillRegistry can register and retrieve skills."""
        skill_dir = tmp_path / "reg_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: reg_skill\ndescription: Registered skill\n---\n# Instructions\nTest."
        )

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)

        registry = SkillRegistry()
        registry.register_skill(skill)
        retrieved = registry.get_skill("reg_skill")

        assert retrieved is not None
        assert retrieved.name == "reg_skill"

    def test_registry_list_skills(self, tmp_path):
        """SkillRegistry lists all registered skills."""
        skill1_dir = tmp_path / "skill1"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\nname: skill1\ndescription: First skill\ncategory: cat1\n---\n# Instructions\nTest 1."
        )

        skill2_dir = tmp_path / "skill2"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text(
            "---\nname: skill2\ndescription: Second skill\ncategory: cat2\n---\n# Instructions\nTest 2."
        )

        loader = SkillLoader()
        registry = SkillRegistry()

        registry.register_skill(loader.load_skill(skill1_dir))
        registry.register_skill(loader.load_skill(skill2_dir))

        skills = registry.list_skills()
        assert len(skills) == 2

    def test_registry_get_nonexistent(self):
        """SkillRegistry.get_skill returns None for missing skill."""
        registry = SkillRegistry()
        result = registry.get_skill("nonexistent")
        assert result is None

    def test_registry_load_skills_from_directory(self, tmp_path):
        """SkillRegistry can load skills from a directory."""
        skill_dir = tmp_path / "load_test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: load_test\ndescription: Test skill\ncategory: test\n---\n# Instructions\nTest."
        )

        registry = SkillRegistry()
        skills = registry.load_skills_from_directory(tmp_path)

        assert len(skills) == 1
        assert skills[0].name == "load_test"

    def test_registry_categories(self, tmp_path):
        """SkillRegistry returns unique categories."""
        skill1_dir = tmp_path / "cat1_skill"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            "---\nname: cat1\ndescription: Cat 1\ncategory: testing\n---\n# Instructions\nTest."
        )

        skill2_dir = tmp_path / "cat2_skill"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text(
            "---\nname: cat2\ndescription: Cat 2\ncategory: tools\n---\n# Instructions\nTest."
        )

        registry = SkillRegistry()
        registry.load_skills_from_directory(tmp_path)

        categories = registry.get_categories()
        assert "testing" in categories
        assert "tools" in categories


class TestSkillCache:
    """Tests for SkillCache."""

    def test_cache_init(self):
        """SkillCache initializes."""
        cache = SkillCache()
        assert cache is not None

    def test_cache_put_and_get(self):
        """SkillCache can store and retrieve skills."""
        cache = SkillCache(check_modification=False)
        mock_skill = MagicMock(spec=Skill)
        mock_skill.name = "cached_skill"

        cache.put("cached_skill", mock_skill)
        result = cache.get("cached_skill")

        assert result is mock_skill

    def test_cache_get_missing(self):
        """SkillCache.get returns None for missing key."""
        cache = SkillCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_clear(self):
        """SkillCache.clear removes all entries."""
        cache = SkillCache(check_modification=False)
        mock_skill = MagicMock(spec=Skill)
        cache.put("skill1", mock_skill)
        cache.put("skill2", mock_skill)

        cache.clear()

        assert cache.get("skill1") is None
        assert cache.get("skill2") is None

    def test_cache_invalidate(self):
        """SkillCache.invalidate removes specific skill."""
        cache = SkillCache(check_modification=False)
        mock_skill = MagicMock(spec=Skill)
        mock_skill.name = "test_skill"

        cache.put("test_skill", mock_skill)
        assert cache.get("test_skill") is not None

        cache.invalidate("test_skill")
        assert cache.get("test_skill") is None

    def test_cache_lru_eviction(self):
        """SkillCache evicts LRU when at capacity."""
        cache = SkillCache(max_size=2, check_modification=False)
        for i in range(3):
            mock_skill = MagicMock(spec=Skill)
            mock_skill.name = f"skill_{i}"
            cache.put(f"skill_{i}", mock_skill)

        assert cache.size == 2
