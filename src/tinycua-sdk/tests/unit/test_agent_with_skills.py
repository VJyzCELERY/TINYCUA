"""Integration tests for agent with skills (INT-04).

Converts targets: 01_single_skill, 02_multiple_skills, 03_dynamic_add_skills,
04_add_skills_list, 05_duplicate_skill_dedup
"""

import pytest

from tinycua_sdk import Agent, LanguageModel, Skill


class TestInt04AgentWithSkills:
    """Test suite for agent skill injection patterns."""

    @pytest.mark.asyncio
    async def test_int_01_single_skill(self, mock_llm_client):
        """Target 4.1: Agent with one skill includes its instructions."""
        coding_skill = Skill(
            name="python_expert",
            description="Write idiomatic Python code.",
            instructions=(
                "When writing Python code, follow PEP 8, use type hints, "
                "prefer dataclasses over raw dicts."
            ),
        )

        agent = Agent(
            llm_model=LanguageModel(),
            skills=[coding_skill],
        )

        response = await agent.run("Write a hello world function.", stream=False)
        assert isinstance(response, str)
        assert len(response) > 0

        call_kwargs = mock_llm_client.call_args[1]
        messages =         call_kwargs["json"]["input"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[python_expert]" in system_msg["content"]
        assert "PEP 8" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_int_02_multiple_skills(self, mock_llm_client):
        """Target 4.2: Multiple skills appear in registration order."""
        skill_a = Skill(name="s1", description="First", instructions="Instruction A.")
        skill_b = Skill(name="s2", description="Second", instructions="Instruction B.")

        agent = Agent(
            llm_model=LanguageModel(),
            skills=[skill_a, skill_b],
        )

        response = await agent.run("Hello.", stream=False)
        assert isinstance(response, str)
        assert len(response) > 0

        call_kwargs = mock_llm_client.call_args[1]
        messages =         call_kwargs["json"]["input"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[s1]" in system_msg["content"]
        assert "[s2]" in system_msg["content"]
        assert "Instruction A." in system_msg["content"]
        assert "Instruction B." in system_msg["content"]
        assert system_msg["content"].index("[s1]") < system_msg["content"].index("[s2]")

    @pytest.mark.asyncio
    async def test_int_03_dynamic_add_skills(self, mock_llm_client):
        """Target 4.3: Skills added after construction work on next run."""
        agent = Agent(llm_model=LanguageModel())

        docs_skill = Skill(
            name="documentarian",
            description="Write clear documentation.",
            instructions="Use Google-style docstrings and add a usage example.",
        )
        agent.add_skills(docs_skill)

        response = await agent.run("Now document that function.", stream=False)
        assert isinstance(response, str)
        assert len(response) > 0

        call_kwargs = mock_llm_client.call_args[1]
        messages =         call_kwargs["json"]["input"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[documentarian]" in system_msg["content"]
        assert "Google-style docstrings" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_int_04_add_skills_list(self, mock_llm_client):
        """Target 4.3: add_skills() accepts a list of skills."""
        coding = Skill(
            name="python_expert",
            description="Write Python code",
            instructions="Follow PEP 8.",
        )
        docs = Skill(
            name="documentarian",
            description="Write docs",
            instructions="Use Google-style docstrings.",
        )

        agent = Agent(llm_model=LanguageModel())
        agent.add_skills([coding, docs])

        response = await agent.run("Hello.", stream=False)
        assert isinstance(response, str)
        assert len(response) > 0

        call_kwargs = mock_llm_client.call_args[1]
        messages =         call_kwargs["json"]["input"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[python_expert]" in system_msg["content"]
        assert "[documentarian]" in system_msg["content"]
        assert "PEP 8" in system_msg["content"]
        assert "Google-style docstrings" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_int_05_duplicate_skill_dedup(self, mock_llm_client):
        """Target 4.3: Adding a skill with existing name silently skips it."""
        original = Skill(
            name="skill_x",
            description="Original",
            instructions="Original instructions.",
        )
        duplicate = Skill(
            name="skill_x",
            description="Duplicate name",
            instructions="Duplicate instructions.",
        )
        other = Skill(
            name="skill_y",
            description="Other",
            instructions="Other instructions.",
        )

        agent = Agent(llm_model=LanguageModel(), skills=[original])
        agent.add_skills([other, duplicate])

        response = await agent.run("Hello.", stream=False)
        assert isinstance(response, str)
        assert len(response) > 0

        call_kwargs = mock_llm_client.call_args[1]
        messages =         call_kwargs["json"]["input"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "[skill_x]" in system_msg["content"]
        assert "[skill_y]" in system_msg["content"]
        assert system_msg["content"].count("[skill_x]") == 1
        assert "Original instructions." in system_msg["content"]
        assert "Duplicate instructions." not in system_msg["content"]
