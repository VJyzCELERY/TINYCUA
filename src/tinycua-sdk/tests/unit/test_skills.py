"""Tests for Skill dataclass, Skill.load(), and SkillRegistry."""



class TestSkillConstruction:
    """Tests for Skill construction."""

    def test_skill_default_construction(self):
        """Skill can be constructed with minimal parameters."""
        from tinycua_sdk import Skill

        skill = Skill(name="coder", description="", instructions="")
        assert skill.name == "coder"
        assert skill.description == ""
        assert skill.instructions == ""
        assert skill.metadata == {}

    def test_skill_full_construction(self):
        """Skill can be constructed with all parameters."""
        from tinycua_sdk import Skill

        skill = Skill(
            name="coder",
            description="Write code",
            instructions="Write clean code.",
            metadata={"author": "test"},
        )
        assert skill.name == "coder"
        assert skill.description == "Write code"
        assert skill.instructions == "Write clean code."
        assert skill.metadata == {"author": "test"}

    def test_skill_to_dict(self):
        """Skill.to_dict() returns a plain dict."""
        from tinycua_sdk import Skill

        skill = Skill(name="coder", description="Write code", instructions="Do code", metadata={"author": "test"})
        d = skill.to_dict()
        assert d["name"] == "coder"
        assert d["description"] == "Write code"
        assert d["instructions"] == "Do code"
        assert d["metadata"] == {"author": "test"}

    def test_skill_from_dict(self):
        """Skill.from_dict() reconstructs a Skill."""
        from tinycua_sdk import Skill

        data = {
            "name": "coder",
            "description": "Write code",
            "instructions": "Write clean code.",
            "metadata": {"author": "test"},
        }
        skill = Skill.from_dict(data)
        assert skill.name == "coder"
        assert skill.description == "Write code"
        assert skill.instructions == "Write clean code."
        assert skill.metadata == {"author": "test"}

    def test_skill_round_trip_dict(self):
        """Skill.to_dict() and Skill.from_dict() are round-trippable."""
        from tinycua_sdk import Skill

        original = Skill(
            name="coder",
            description="Write code",
            instructions="Write clean code.",
            metadata={"author": "test"},
        )
        restored = Skill.from_dict(original.to_dict())
        assert restored == original





class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_registry_explicit_instance(self):
        """SkillRegistry can be instantiated explicitly."""
        from tinycua_sdk import SkillRegistry

        registry = SkillRegistry()
        assert registry is not None

    def test_registry_not_singleton(self):
        """SkillRegistry instances are independent."""
        from tinycua_sdk import SkillRegistry, Skill

        r1 = SkillRegistry()
        r2 = SkillRegistry()
        r1.register(Skill(name="a", description="", instructions=""))
        assert r2.get("a") is None

    def test_registry_register_and_get(self):
        """SkillRegistry can register and retrieve skills."""
        from tinycua_sdk import SkillRegistry, Skill

        registry = SkillRegistry()
        skill = Skill(name="coder", description="Write code", instructions="Write clean code.")
        registry.register(skill)
        retrieved = registry.get("coder")
        assert retrieved is not None
        assert retrieved.name == "coder"
