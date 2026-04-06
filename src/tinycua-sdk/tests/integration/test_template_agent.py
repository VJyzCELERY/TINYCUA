"""Integration tests for template-based agent creation."""

import pytest

from tinycua_sdk import Agent
from tinycua_sdk.agent.loop import DefaultLoop, ReactLoop, PlanLoop


class TestFromTemplate:
    """Tests for Agent.from_template method."""

    def test_from_template_coder(self):
        """Agent.from_template('coder') creates agent."""
        agent = Agent.from_template("coder")
        assert agent.name == "coder"
        assert "expert programmer" in agent.system_prompt.lower()
        assert agent.model == "gpt-4o-mini"
        assert agent.provider == "openai"

    def test_from_template_researcher(self):
        """Agent.from_template('researcher') creates agent."""
        agent = Agent.from_template("researcher")
        assert agent.name == "researcher"
        assert "research" in agent.system_prompt.lower()
        assert agent.model == "gpt-4o-mini"
        assert agent.provider == "openai"

    def test_from_template_assistant(self):
        """Agent.from_template('assistant') creates agent."""
        agent = Agent.from_template("assistant")
        assert agent.name == "assistant"
        assert "helpful" in agent.system_prompt.lower()
        assert agent.model == "gpt-4o-mini"
        assert agent.provider == "openai"

    def test_from_template_with_overrides(self):
        """Customization via overrides works."""
        agent = Agent.from_template(
            "coder", overrides={"model": "gpt-4o", "provider": "ollama"}
        )
        assert agent.model == "gpt-4o"
        assert agent.provider == "ollama"
        # Original values preserved
        assert agent.name == "coder"

    def test_from_template_with_policy_overrides(self):
        """Policy overrides work correctly."""
        agent = Agent.from_template("coder", overrides={"policy": {"temperature": 0.3}})
        assert agent.policy.temperature == 0.3
        # Original values preserved
        assert agent.policy.max_tool_calls == 15

    def test_from_template_invalid_name(self):
        """Invalid template raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Agent.from_template("invalid_template")
        assert "not found" in str(exc_info.value)

    def test_from_template_case_insensitive(self):
        """Template name is case-insensitive."""
        agent = Agent.from_template("CODER")
        assert agent.name == "coder"
        agent = Agent.from_template("Researcher")
        assert agent.name == "researcher"

    def test_from_template_with_loop_default(self):
        """Default loop is resolved correctly."""
        agent = Agent.from_template("assistant")
        assert agent.config.loop is not None
        assert isinstance(agent.config.loop, DefaultLoop)

    def test_from_template_with_loop_react(self):
        """React loop is resolved correctly."""
        agent = Agent.from_template("researcher")
        assert agent.config.loop is not None
        assert isinstance(agent.config.loop, ReactLoop)

    def test_from_template_with_loop_plan(self):
        """Plan loop can be specified via overrides."""
        agent = Agent.from_template("assistant", overrides={"loop": "plan"})
        assert agent.config.loop is not None
        assert isinstance(agent.config.loop, PlanLoop)

    def test_from_template_skills_handling(self):
        """Skills are handled through overrides."""
        # Skills are passed via overrides - verify agent is created successfully
        agent = Agent.from_template("coder", overrides={"skills": ["skill1", "skill2"]})
        # Agent should be created without error
        assert agent.name == "coder"
        assert agent.config is not None

    def test_from_template_tools_resolution(self):
        """Tool strings are resolved to Tool instances."""
        agent = Agent.from_template("coder")
        # Tools should be resolved (or empty list if not registered)
        assert isinstance(agent.tools, list)

    def test_from_template_keywords_passed(self):
        """Keywords are passed to agent."""
        agent = Agent.from_template("coder")
        # Keywords should be available
        assert agent.keywords is not None
        assert "code" in agent.keywords

    def test_from_template_additional_kwargs(self):
        """Additional kwargs are passed to Agent constructor."""
        agent = Agent.from_template(
            "coder", api_key="test-key", base_url="http://localhost:8000"
        )
        assert agent.config.api_key == "test-key"
        assert agent.config.base_url == "http://localhost:8000"
