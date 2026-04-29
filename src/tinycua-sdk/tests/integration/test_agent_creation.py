"""Integration tests for Agent creation and initialization."""

import pytest
from unittest.mock import MagicMock, patch
from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.config import AgentPolicy
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry


class TestAgentCreation:
    """Integration tests for agent creation."""

    def test_create_agent_with_all_options(self):
        """Test creating agent with all configuration options."""
        from tinycua_sdk.tools.decorators import Tool

        mock_tool = Tool(name="test_tool", description="A test tool")

        policy = AgentPolicy(max_tool_calls=5, parallel_tool_calls=False)
        llm_model = LLMModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="test-key",
            system_prompt="You are a helpful assistant.",
        )

        agent = Agent(
            name="test-agent",
            llm_model=llm_model,
            tools=[mock_tool],
            policy=policy,
        )

        assert agent.name == "test-agent"
        assert agent.model == "qwen/qwen3.5-9b"
        assert agent.provider == "openai-compatible"
        assert len(agent.tools) == 1

    def test_create_agent_with_minimal_config(self):
        """Test creating agent with only required options."""
        llm_model = LLMModel(
            provider="test-provider",
            model_name="test-model",
        )
        agent = Agent(
            name="minimal-agent",
            llm_model=llm_model,
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
        for entry in sorted(tmp_path.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                skill_md = entry / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text(encoding="utf-8")
                    skill = Skill.load(content)
                    skill.source = str(entry)
                    registry.register(skill)

        llm_model = LLMModel(
            provider="test-provider",
            model_name="test-model",
        )
        agent = Agent(
            name="skill-agent",
            llm_model=llm_model,
        )

        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "test_skill"

    def test_agent_model_property(self):
        """Test agent model property is accessible."""
        llm_model = LLMModel(
            provider="test-provider",
            model_name="test-model",
        )
        agent = Agent(
            name="update-test",
            llm_model=llm_model,
        )

        assert agent.model == "test-model"

    def test_agent_provider_property(self):
        """Test agent provider property is accessible."""
        llm_model = LLMModel(
            provider="test-provider",
            model_name="test-model",
        )
        agent = Agent(
            name="provider-test",
            llm_model=llm_model,
        )

        assert agent.provider == "test-provider"


class TestAgentToolsIntegration:
    """Integration tests for agent with tools."""

    def test_agent_with_memory_tools(self):
        """Test agent with memory tools attached."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.agent.llm_model import LLMModel

        @tool
        def remember(content: str) -> str:
            """Remember something."""
            return f"Remembered: {content}"

        @tool
        def recall(query: str) -> str:
            """Recall something."""
            return f"Recalled: {query}"

        llm_model = LLMModel(
            provider="test-provider",
            model_name="test-model",
        )
        agent = Agent(
            name="memory-agent",
            llm_model=llm_model,
            tools=[remember, recall],
        )

        assert len(agent.tools) == 2
        tool_names = [t.name for t in agent.tools]
        assert "remember" in tool_names
        assert "recall" in tool_names

    def test_agent_tool_dispatch(self):
        """Test agent can dispatch to tools."""
        from tinycua_sdk.tools import tool
        from tinycua_sdk.agent.llm_model import LLMModel

        @tool
        def add(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y

        llm_model = LLMModel(
            provider="test-provider",
            model_name="test-model",
        )
        agent = Agent(
            name="dispatch-agent",
            llm_model=llm_model,
            tools=[add],
        )

        tool_instance = agent.tools[0]
        result = tool_instance.invoke(x=2, y=3)
        assert result == 5
