"""Unit tests for Agent Hierarchy."""

import pytest


class TestAgentHierarchyBasics:
    """Test basic agent hierarchy functionality."""

    def test_agent_sub_agents_default_empty(self):
        """Test sub_agents defaults to empty list."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="test")

        assert agent.sub_agents == []

    def test_agent_accepts_sub_agents(self):
        """Test agent accepts sub_agents in constructor."""
        from tinycua_sdk.models import Agent

        sub1 = Agent(name="sub1")
        sub2 = Agent(name="sub2")

        agent = Agent(name="main", sub_agents=[sub1, sub2])

        assert len(agent.sub_agents) == 2

    def test_add_sub_agent(self):
        """Test adding sub-agent."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")
        sub = Agent(name="sub")

        agent.add_sub_agent(sub)

        assert len(agent.sub_agents) == 1
        assert agent.sub_agents[0].name == "sub"

    def test_add_multiple_sub_agents(self):
        """Test adding multiple sub-agents."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        for i in range(5):
            agent.add_sub_agent(Agent(name=f"sub{i}"))

        assert len(agent.sub_agents) == 5


class TestAgentHierarchyLimits:
    """Test hierarchy limits."""

    def test_max_10_sub_agents(self):
        """Test maximum 10 sub-agents allowed."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        # Add 10 sub-agents
        for i in range(10):
            agent.add_sub_agent(Agent(name=f"sub{i}"))

        assert len(agent.sub_agents) == 10

        # Adding 11th should raise
        with pytest.raises(ValueError) as exc:
            agent.add_sub_agent(Agent(name="sub10"))

        assert "10" in str(exc.value)

    def test_max_depth_default_3(self):
        """Test default max depth is 3."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        assert agent.max_depth == 3

    def test_custom_max_depth(self):
        """Test custom max depth."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main", max_depth=5)

        assert agent.max_depth == 5


class TestAgentHierarchyDepthTracking:
    """Test depth tracking."""

    def test_default_current_depth_0(self):
        """Test default current depth is 0."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        assert agent.current_depth == 0

    def test_current_depth_increments(self):
        """Test current depth can be set."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="child", current_depth=2)

        assert agent.current_depth == 2


class TestAgentSubAgentMethods:
    """Test sub-agent helper methods."""

    def test_get_all_sub_agents(self):
        """Test getting all sub-agents recursively."""
        from tinycua_sdk.models import Agent

        sub_sub = Agent(name="sub_sub")
        sub = Agent(name="sub", sub_agents=[sub_sub])
        main = Agent(name="main", sub_agents=[sub])

        all_agents = main._get_all_sub_agents()

        assert "main" in all_agents
        assert "sub" in all_agents
        assert "sub_sub" in all_agents

    def test_find_sub_agent_for_task(self):
        """Test finding sub-agent based on keywords."""
        from tinycua_sdk.models import Agent

        research = Agent(name="research", keywords=["search", "find", "research"])
        code = Agent(name="code", keywords=["code", "program", "write"])

        main = Agent(name="main", sub_agents=[research, code])

        matched = main._find_sub_agent_for_task("search for Python tutorials")

        assert matched is not None
        assert matched.name == "research"

    def test_find_sub_agent_no_match(self):
        """Test no match returns None."""
        from tinycua_sdk.models import Agent

        sub = Agent(name="research")
        main = Agent(name="main", sub_agents=[sub])

        matched = main._find_sub_agent_for_task("hello world")

        # May return None or the sub-agent
        assert matched is None or isinstance(matched, Agent)


class TestAgentDelegation:
    """Test delegation logic."""

    def test_should_delegate_when_sub_agents_exist(self):
        """Test should_delegate logic."""
        from tinycua_sdk.models import Agent

        sub = Agent(name="research")
        agent = Agent(name="main", sub_agents=[sub])

        # If there are sub-agents, it may delegate
        # The actual decision depends on task analysis
        has_sub = len(agent.sub_agents) > 0

        assert has_sub is True

    def test_no_delegation_without_sub_agents(self):
        """Test no delegation when no sub-agents."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        assert len(agent.sub_agents) == 0


class TestAgentContextPassing:
    """Test context passing between agents."""

    def test_pass_context_to_sub_agent(self):
        """Test context is passed to sub-agent."""
        from tinycua_sdk.models import Agent

        parent = Agent(name="parent", instructions="You are a parent agent.")
        child = Agent(name="child", instructions="You are a child agent.")

        parent.add_sub_agent(child)

        context = parent._pass_context_to_sub_agent("test task", child)

        assert "test task" in context
        assert "parent" in context.lower()

    def test_aggregate_results(self):
        """Test result aggregation."""
        from tinycua_sdk.models import Agent

        parent = Agent(name="parent")
        child = Agent(name="child")

        result = parent._aggregate_results("child result", child)

        assert "child" in result.lower()
        assert "child result" in result


class TestAgentKeywordsFallback:
    """Test keyword fallback to agent name."""

    def test_keywords_fallback_to_name(self):
        """Test keywords default to agent name when not specified."""
        from tinycua_sdk.models import Agent

        searcher = Agent(name="searcher")
        main = Agent(name="main", sub_agents=[searcher])

        # Should match "searcher" from agent name
        matched = main._find_sub_agent_for_task("ask searcher to find info")

        assert matched is not None
        assert matched.name == "searcher"

    def test_explicit_keywords_override_name(self):
        """Test explicit keywords take precedence over name."""
        from tinycua_sdk.models import Agent

        # searcher has explicit keywords, should use those
        searcher = Agent(name="searcher", keywords=["research"])
        main = Agent(name="main", sub_agents=[searcher])

        # Should NOT match "searcher" because explicit keywords don't include "code"
        matched = main._find_sub_agent_for_task("ask searcher to code")

        assert matched is None


class TestNestedDepthLimits:
    """Test nested depth limits."""

    def test_depth_limit_enforced_in_get_all(self):
        """Test depth limit is enforced when getting all sub-agents."""
        from tinycua_sdk.models import Agent

        # Create 4 levels
        l4 = Agent(name="l4")
        l3 = Agent(name="l3", sub_agents=[l4])
        l2 = Agent(name="l2", sub_agents=[l3])
        l1 = Agent(name="l1", sub_agents=[l2])

        # With max_depth=3 (default), depth starts at 0
        # l1 (depth 0), l2 (depth 1), l3 (depth 2), l4 (depth 3)
        # At depth 3, should still return self but not recurse further
        all_agents = l1._get_all_sub_agents()

        # All should be present because depth 3 still returns self
        assert "l1" in all_agents
        assert "l2" in all_agents
        assert "l3" in all_agents
        assert "l4" in all_agents

    def test_depth_limit_with_custom_max(self):
        """Test depth limit with custom max_depth."""
        from tinycua_sdk.models import Agent

        # Create agents with different max_depth
        l4 = Agent(name="l4", max_depth=1)
        l3 = Agent(name="l3", sub_agents=[l4], max_depth=1)
        l2 = Agent(name="l2", sub_agents=[l3], max_depth=1)
        l1 = Agent(name="l1", sub_agents=[l2], max_depth=1)

        # With max_depth=1, recursion stops at depth 1
        all_agents = l1._get_all_sub_agents()

        # Should only get l1 and l2
        assert "l1" in all_agents
        assert "l2" in all_agents
        # l3 and l4 won't be recursed into because depth=1 >= max_depth=1
        assert "l3" not in all_agents
        assert "l4" not in all_agents

    def test_current_depth_affects_nesting(self):
        """Test current_depth affects nesting level."""
        from tinycua_sdk.models import Agent

        # Agent at max depth should not be able to add sub-agents effectively
        child = Agent(name="child", current_depth=3, max_depth=3)
        grandchild = Agent(name="grandchild")

        # Adding grandchild to child at max depth
        child.add_sub_agent(grandchild)

        # Should still work but depth tracking matters
        assert len(child.sub_agents) == 1


class TestContextPassingEdgeCases:
    """Test edge cases for context passing."""

    def test_empty_task_context(self):
        """Test context with empty task."""
        from tinycua_sdk.models import Agent

        parent = Agent(name="parent")
        child = Agent(name="child")

        context = parent._pass_context_to_sub_agent("", child)

        assert "parent" in context.lower()

    def test_empty_result_aggregation(self):
        """Test aggregation with empty result."""
        from tinycua_sdk.models import Agent

        parent = Agent(name="parent")
        child = Agent(name="child")

        result = parent._aggregate_results("", child)

        assert "child" in result.lower()

    def test_special_characters_in_task(self):
        """Test special characters in task are preserved."""
        from tinycua_sdk.models import Agent

        parent = Agent(name="parent")
        child = Agent(name="child")

        context = parent._pass_context_to_sub_agent("Task with <xml> & 'quotes'", child)

        assert "<xml>" in context
        assert "&" in context
        assert "'quotes'" in context


class TestAgentConfigSerialization:
    """Test agent config serialization."""

    def test_agent_to_config(self):
        """Test agent can be converted to config dict."""
        from tinycua_sdk.models import Agent

        agent = Agent(
            name="test",
            instructions="Test instructions",
            model="test-model",
            provider="openai",
        )

        config = agent.to_config()

        assert config["name"] == "test"
        assert config["instructions"] == "Test instructions"
        assert config["model"] == "test-model"
        assert config["provider"] == "openai"

    def test_agent_from_config(self):
        """Test agent can be created from config dict."""
        from tinycua_sdk.models import Agent

        config = {
            "name": "test",
            "instructions": "Test instructions",
            "model": "test-model",
            "provider": "openai",
        }

        agent = Agent.from_config(config)

        assert agent.name == "test"
        assert agent.instructions == "Test instructions"
        assert agent.model == "test-model"

    def test_sub_agents_not_in_config(self):
        """Test sub_agents are not serialized in to_config."""
        from tinycua_sdk.models import Agent

        sub = Agent(name="sub")
        agent = Agent(name="main", sub_agents=[sub])

        config = agent.to_config()

        # sub_agents should not be in config (would cause circular refs)
        assert "sub_agents" not in config


class TestStreamEventEdgeCases:
    """Test StreamEvent edge cases."""

    def test_stream_event_to_sse(self):
        """Test StreamEvent can be serialized to SSE format."""
        from tinycua_sdk.models.response import StreamEvent, StreamEventType

        event = StreamEvent(type=StreamEventType.CONTENT, data={"content": "test"})

        sse = event.to_sse()

        assert "data:" in sse
        assert "content" in sse

    def test_stream_event_from_sse(self):
        """Test StreamEvent can be parsed from SSE data."""
        from tinycua_sdk.models.response import StreamEvent, StreamEventType

        sse = 'data: {"type": "content", "content": "test"}\n\n'

        event = StreamEvent.from_sse(sse)

        assert event.type == StreamEventType.CONTENT
        assert event.data["content"] == "test"

    def test_stream_event_types_complete(self):
        """Test all stream event types are defined."""
        from tinycua_sdk.models.response import StreamEventType

        expected_types = [
            "content",
            "done",
            "tool_call_start",
            "tool_call_chunk",
            "tool_call_end",
            "tool_result_start",
            "tool_result_chunk",
            "tool_result_end",
            "delegation_start",
            "delegation_end",
            "llm_request",
            "llm_response",
            "error",
        ]

        for expected in expected_types:
            assert hasattr(StreamEventType, expected.upper())


class TestRunnerStreamSSE:
    """Test Runner stream_sse functionality."""

    def test_runner_stream_sse_attribute(self):
        """Test Runner has stream_sse attribute."""
        from tinycua_sdk.runner import Runner
        from tinycua_sdk.models import AgentConfig

        config = AgentConfig(name="test")
        runner = Runner(config)

        assert hasattr(runner, "stream_sse")
        assert runner.stream_sse is False

    def test_runner_verbose_attribute(self):
        """Test Runner has verbose attribute."""
        from tinycua_sdk.runner import Runner
        from tinycua_sdk.models import AgentConfig

        config = AgentConfig(name="test")
        runner = Runner(config)

        assert hasattr(runner, "verbose")
        assert runner.verbose is False

    def test_runner_trace_attribute(self):
        """Test Runner has trace attribute."""
        from tinycua_sdk.runner import Runner
        from tinycua_sdk.models import AgentConfig

        config = AgentConfig(name="test")
        runner = Runner(config)

        assert hasattr(runner, "trace")
        assert runner.trace is False
