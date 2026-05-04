"""Integration tests for Skills System."""

import pytest
from tinycua_sdk import Agent, LLMModel, Skill, SkillRegistry


class TestSkillsIntegration:
    """Integration tests for skills."""

    def test_add_single_skill(self):
        """Add one skill to agent."""
        agent = Agent(llm_model=LLMModel())
        agent.add_skills(Skill(name="coder", description="", instructions=""))
        assert len(agent.skills) == 1

    def test_add_multiple_skills(self):
        """Add list of skills."""
        agent = Agent(llm_model=LLMModel())
        agent.add_skills([Skill(name="a", description="", instructions=""), Skill(name="b", description="", instructions="")])
        assert len(agent.skills) == 2

    def test_skill_at_construction(self):
        """Skills passed at Agent construction."""
        agent = Agent(llm_model=LLMModel(), skills=[Skill(name="coder", description="", instructions="")])
        assert len(agent.skills) == 1

    @pytest.mark.asyncio
    async def test_agent_with_skill_run(self, mock_llm_client):
        """Run agent with skill attached."""
        agent = Agent(
            llm_model=LLMModel(),
            skills=[Skill(name="coder", description="", instructions="Write code")],
        )
        response = await agent.run("Write a function")
        assert response == "Mocked response"

    def test_skill_registry_load(self):
        """Load skills into registry."""
        registry = SkillRegistry()
        registry.register(Skill(name="a", description="", instructions=""))
        registry.register(Skill(name="b", description="", instructions=""))
        assert len(registry.list_skills()) == 2

    def test_registry_not_singleton(self):
        """Registries are independent (no global singleton)."""
        r1 = SkillRegistry()
        r2 = SkillRegistry()
        r1.register(Skill(name="a", description="", instructions=""))
        assert r2.get("a") is None

    def test_skill_config_round_trip(self):
        """Serialize and deserialize skill."""
        original = Skill(name="test", description="", instructions="Do something")
        d = original.to_dict()
        restored = Skill.from_dict(d)
        assert restored.name == "test"
        assert restored.instructions == "Do something"
