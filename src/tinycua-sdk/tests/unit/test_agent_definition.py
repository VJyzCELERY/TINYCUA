"""Tests for AgentDefinition class."""

import pytest

from tinycua_sdk.agent.config import AgentPolicy
from tinycua_sdk.agent.definition import AgentDefinition
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.tools.decorators import tool


class TestAgentDefinition:
    """Test AgentDefinition properties, config, and serialization."""

    def test_agent_definition_is_not_abstract(self):
        """Test AgentDefinition can be instantiated directly."""
        agent = AgentDefinition(name="test")
        assert agent.name == "test"

    def test_agent_definition_initialization(self):
        """Test AgentDefinition initializes with defaults."""
        agent = AgentDefinition(
            name="test",
            instructions="You are a test agent.",
            llm_model=LLMModel(model_name="gpt-4o-mini"),
        )
        assert agent.name == "test"
        assert agent.instructions == "You are a test agent."
        assert agent.model == "gpt-4o-mini"
        assert isinstance(agent.policy, AgentPolicy)

    def test_agent_definition_with_tools(self):
        """Test AgentDefinition accepts tools."""

        @tool()
        def my_tool() -> None:
            """A tool."""
            pass

        agent = AgentDefinition(name="test", instructions="...", tools=[my_tool])
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "my_tool"

    def test_agent_definition_to_config(self):
        """Test AgentDefinition serializes to config dict."""
        agent = AgentDefinition(name="my-agent", instructions="Be helpful.")
        config = agent.to_config()

        assert config["name"] == "my-agent"
        assert config["instructions"] == "Be helpful."
        assert "policy" in config

    def test_agent_definition_from_config(self):
        """Test AgentDefinition can be created from config dict."""
        config = {
            "name": "test",
            "instructions": "Test instructions",
            "llm_model": {
                "model_name": "test-model",
                "provider": "openai",
            },
        }

        agent = AgentDefinition.from_config(config)

        assert agent.name == "test"
        assert agent.instructions == "Test instructions"
        assert agent.model == "test-model"

    def test_sub_agents_not_in_config(self):
        """Test sub_agents are not serialized in to_config."""
        sub = AgentDefinition(name="sub")
        agent = AgentDefinition(name="main", sub_agents=[sub])

        config = agent.to_config()

        # sub_agents should not be in config (would cause circular refs)
        assert "sub_agents" not in config

    def test_add_sub_agent(self):
        """Test adding sub-agent."""
        agent = AgentDefinition(name="main")
        sub = AgentDefinition(name="sub")

        agent.add_sub_agent(sub)

        assert len(agent.sub_agents) == 1
        assert agent.sub_agents[0].name == "sub"

    def test_max_10_sub_agents(self):
        """Test maximum 10 sub-agents allowed."""
        agent = AgentDefinition(name="main")

        for i in range(10):
            agent.add_sub_agent(AgentDefinition(name=f"sub{i}"))

        assert len(agent.sub_agents) == 10

        with pytest.raises(ValueError) as exc:
            agent.add_sub_agent(AgentDefinition(name="sub10"))

        assert "10" in str(exc.value)

    def test_get_all_sub_agents(self):
        """Test getting all sub-agents recursively."""
        sub_sub = AgentDefinition(name="sub_sub")
        sub = AgentDefinition(name="sub", sub_agents=[sub_sub])
        main = AgentDefinition(name="main", sub_agents=[sub])

        all_agents = main._get_all_sub_agents()

        assert "main" in all_agents
        assert "sub" in all_agents
        assert "sub_sub" in all_agents

    def test_find_sub_agent_for_task(self):
        """Test finding sub-agent based on keywords."""
        research = AgentDefinition(name="research", keywords=["search", "find"])
        code = AgentDefinition(name="code", keywords=["code", "program"])

        main = AgentDefinition(name="main", sub_agents=[research, code])

        matched = main._find_sub_agent_for_task("search for Python tutorials")

        assert matched is not None
        assert matched.name == "research"

    def test_pass_context_to_sub_agent(self):
        """Test context is passed to sub-agent."""
        parent = AgentDefinition(name="parent", instructions="You are a parent agent.")
        child = AgentDefinition(name="child", instructions="You are a child agent.")

        parent.add_sub_agent(child)

        context = parent._pass_context_to_sub_agent("test task", child)

        assert "test task" in context
        assert "parent" in context.lower()

    def test_aggregate_results(self):
        """Test result aggregation."""
        parent = AgentDefinition(name="parent")
        child = AgentDefinition(name="child")

        result = parent._aggregate_results("child result", child)

        assert "child" in result.lower()
        assert "child result" in result

    def test_str_representation(self):
        """Test __str__ returns formatted agent details."""
        agent = AgentDefinition(
            name="test-agent",
            llm_model=LLMModel(model_name="gpt-4o-mini", provider="openai"),
        )

        result = str(agent)

        assert "test-agent" in result
        assert "gpt-4o-mini" in result
        assert "openai" in result

    def test_add_tool(self):
        """Test adding a single tool."""

        @tool()
        def my_tool() -> None:
            """A tool."""
            pass

        agent = AgentDefinition(name="test")
        agent.add_tool(my_tool)

        assert len(agent.tools) == 1

    def test_add_tools(self):
        """Test adding multiple tools."""

        @tool()
        def tool_a() -> None:
            """Tool A."""
            pass

        @tool()
        def tool_b() -> None:
            """Tool B."""
            pass

        agent = AgentDefinition(name="test")
        agent.add_tools([tool_a, tool_b])

        assert len(agent.tools) == 2
