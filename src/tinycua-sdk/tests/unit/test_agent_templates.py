"""Tests for agent template loading with the new stateless API."""

import pytest


class TestAgentTemplates:
    """Tests for built-in agent templates."""

    def test_coder_template_exists(self):
        """Coder template can be loaded via Agent.from_config."""
        from tinycua_sdk import Agent

        agent = Agent.from_config("coder")
        assert agent.name == "coder"

    def test_researcher_template_exists(self):
        """Researcher template can be loaded via Agent.from_config."""
        from tinycua_sdk import Agent

        agent = Agent.from_config("researcher")
        assert agent.name == "researcher"

    def test_template_llm_override(self):
        """Template-loaded agent can have its LLM overridden."""
        from tinycua_sdk import Agent, LLMModel

        agent = Agent.from_config("coder")
        agent.llm_model = LLMModel(model_name="custom-model")
        assert agent.llm_model.model_name == "custom-model"

    def test_invalid_template_raises(self):
        """Unknown template name raises ValueError."""
        from tinycua_sdk import Agent

        with pytest.raises(ValueError):
            Agent.from_config("nonexistent_template")
