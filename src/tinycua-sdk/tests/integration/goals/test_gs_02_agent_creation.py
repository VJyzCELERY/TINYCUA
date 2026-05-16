"""Integration tests for Agent configuration and creation.

Converts targets: 01_minimal_agent, 02_named_agent, 03_agent_with_policy,
04_agent_with_metadata, 05_obsolete_params_rejected, 06_dynamic_composition,
07_to_config
"""

import pytest

from tinycua_sdk import Agent, AgentPolicy, LanguageModel, Skill, tool


class TestGS02AgentCreation:
    """Test suite for Agent creation patterns and serialization."""

    def test_gs_01_minimal_agent(self):
        """Target 2.1: Create a minimal Agent with no arguments."""
        agent = Agent()

        assert agent.name == "assistant"
        assert agent.instructions == ""
        assert agent.llm_model.model_name == "gpt-4o-mini"
        assert len(agent.tools) == 0
        assert len(agent.skills) == 0

    def test_gs_02_named_agent(self):
        """Target 2.2: Create a named agent with custom instructions and model."""
        agent = Agent(
            name="greeter",
            instructions="You are a friendly greeter.",
            llm_model=LanguageModel(
                provider="openai-compatible",
                model_name="qwen/qwen3.5-9b",
                base_url="http://localhost:1234/v1",
                api_key="dummy",
            ),
        )

        assert agent.name == "greeter"
        assert agent.instructions == "You are a friendly greeter."
        assert agent.llm_model.model_name == "qwen/qwen3.5-9b"

    def test_gs_03_agent_with_policy(self):
        """Target 2.3: Create an agent with custom policy settings."""
        agent = Agent(
            name="researcher",
            instructions="Cite your sources.",
            policy=AgentPolicy(max_tool_calls=15, parallel_tool_calls=True),
        )

        assert agent.policy.max_tool_calls == 15
        assert agent.policy.parallel_tool_calls is True

    def test_gs_04_agent_with_metadata(self):
        """Target 2.4: Create an agent with consumer-defined metadata."""
        agent = Agent(
            name="tagged_assistant",
            instructions="Help the user.",
            metadata={
                "team": "platform",
                "cost_center": "eng-123",
                "version": "2.1.0",
            },
        )

        assert agent.metadata["team"] == "platform"
        assert agent.metadata["cost_center"] == "eng-123"

    def test_gs_05_obsolete_params_rejected(self):
        """Target 2.5: Verify obsolete parameters raise TypeError."""
        obsolete_params = [
            "system_prompt",
            "model",
            "provider",
            "base_url",
            "api_key",
            "mode",
            "backend_url",
            "backend_api_key",
            "backend_headers",
            "agent_id",
            "planning_prompt",
            "short_term_memory",
            "long_term_memory",
            "session_id",
            "sub_agents",
            "max_depth",
            "strip_thinking",
            "backend",
        ]

        for param in obsolete_params:
            with pytest.raises(TypeError) as excinfo:
                Agent(**{param: "test"})
            message = str(excinfo.value)
            assert param in message or "unexpected keyword argument" in message

    def test_gs_06_dynamic_composition(self):
        """Target 2.6: Verify tools and skills can be added after creation."""

        @tool
        def calc(expr: str) -> str:
            """Evaluate expression."""
            return f"expr:{expr}"

        skill = Skill(name="math", description="Math help", instructions="Show work.")

        agent = Agent()
        assert len(agent.tools) == 0
        assert len(agent.skills) == 0

        agent.add_tools(calc)
        agent.add_skills(skill)

        assert len(agent.tools) == 1
        assert agent.tools[0].name == "calc"
        assert len(agent.skills) == 1
        assert agent.skills[0].name == "math"

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        skill_two = Skill(
            name="testing", description="Write tests", instructions="Cover edge cases."
        )
        agent.add_tools([add])
        agent.add_skills([skill_two])

        assert len(agent.tools) == 2
        assert len(agent.skills) == 2

    def test_gs_07_to_config(self):
        """Target 2.7: Verify to_config() captures all fields."""

        @tool
        def calc(expr: str) -> str:
            """Evaluate expression."""
            return f"expr:{expr}"

        skill = Skill(name="math", description="Math help", instructions="Show work.")

        agent = Agent(
            name="tutor",
            instructions="Be patient.",
            llm_model=LanguageModel(model_name="test-model", temperature=0.2),
            tools=[calc],
            skills=[skill],
            metadata={"team": "platform"},
            tool_permissions={"calc": "allow"},
        )

        config = agent.to_config()

        assert config["name"] == "tutor"
        assert config["instructions"] == "Be patient."
        assert config["llm_model"]["model_name"] == "test-model"
        assert config["llm_model"]["temperature"] == 0.2
        assert len(config["tools"]) == 1
        assert config["tools"][0]["name"] == "calc"
        assert len(config["skills"]) == 1
        assert config["skills"][0]["name"] == "math"
        assert config["metadata"]["team"] == "platform"
        assert config["tool_permissions"]["calc"] == "allow"
