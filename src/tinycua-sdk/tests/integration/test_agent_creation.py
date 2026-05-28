"""Integration tests for Agent creation and initialization."""

import pytest
from unittest.mock import MagicMock, patch
from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.config import AgentPolicy
from tinycua_sdk.skills.registry import SkillRegistry


class TestAgentCreation:
    """Integration tests for agent creation."""

    def test_create_agent_with_all_options(self):
        """Test creating agent with all configuration options."""
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"

        policy = AgentPolicy(max_tool_calls=5, parallel_tool_calls=False)

        agent = Agent(
            name="test-agent",
            model="qwen/qwen3.5-9b",
            provider="openai-compatible",
            base_url="http://localhost:1234/v1",
            api_key="test-key",
            tools=[mock_tool],
            policy=policy,
            system_prompt="You are a helpful assistant.",
            mode="local",
        )

        assert agent.name == "test-agent"
        assert agent.model == "qwen/qwen3.5-9b"
        assert agent.provider == "openai-compatible"
        assert len(agent.tools) == 1

    def test_create_agent_with_minimal_config(self):
        """Test creating agent with only required options."""
        agent = Agent(
            name="minimal-agent",
            model="test-model",
            provider="test-provider",
        )

        assert agent.name == "minimal-agent"
        assert agent.model == "test-model"
        assert agent.provider == "test-provider"
        assert agent.tools == []

    def test_create_agent_with_skills(self, tmp_path):
        """Test creating agent with skills registry."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test_skill\ndescription: Test skill\ncategory: testing\n---\n# Instructions\nTest instructions."
        )

        registry = SkillRegistry()
        registry.load_skills_from_directory(tmp_path)

        agent = Agent(
            name="skill-agent",
            model="test-model",
            provider="test-provider",
        )

        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "test_skill"

    def test_agent_model_property(self):
        """Test agent model property is accessible."""
        agent = Agent(
            name="update-test",
            model="test-model",
            provider="test-provider",
        )

        assert agent.model == "test-model"

    def test_agent_provider_property(self):
        """Test agent provider property is accessible."""
        agent = Agent(
            name="provider-test",
            model="test-model",
            provider="test-provider",
        )

        assert agent.provider == "test-provider"


class TestAgentToolsIntegration:
    """Integration tests for agent with tools."""

    def test_agent_with_memory_tools(self):
        """Test agent with memory tools attached."""
        from tinycua_sdk.tools import tool

        @tool
        def remember(content: str) -> str:
            """Remember something."""
            return f"Remembered: {content}"

        @tool
        def recall(query: str) -> str:
            """Recall something."""
            return f"Recalled: {query}"

        agent = Agent(
            name="memory-agent",
            model="test-model",
            provider="test-provider",
            tools=[remember, recall],
        )

        assert len(agent.tools) == 2
        tool_names = [t.name for t in agent.tools]
        assert "remember" in tool_names
        assert "recall" in tool_names

    def test_agent_tool_dispatch(self):
        """Test agent can dispatch to tools."""
        from tinycua_sdk.tools import tool

        @tool
        def add(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y

        agent = Agent(
            name="dispatch-agent",
            model="test-model",
            provider="test-provider",
            tools=[add],
        )

        tool_instance = agent.tools[0]
        result = tool_instance.invoke(x=2, y=3)
        assert result == 5