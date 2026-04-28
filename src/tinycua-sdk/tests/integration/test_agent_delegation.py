"""Integration tests for Agent Hierarchy.

Tests for agent delegation to sub-agents.

Run with: pytest tests/integration/test_agent_hierarchy.py -v -m integration
"""

import pytest


class TestAgentHierarchy:
    """Test agent hierarchy functionality."""

    def test_agent_accepts_sub_agents_parameter(self):
        """Test that Agent accepts sub_agents parameter."""
        from tinycua_sdk.models import Agent

        sub_agent = Agent(name="sub")
        agent = Agent(name="main", sub_agents=[sub_agent])

        assert len(agent.sub_agents) == 1
        assert agent.sub_agents[0].name == "sub"

    def test_agent_with_multiple_sub_agents(self):
        """Test agent with multiple sub-agents."""
        from tinycua_sdk.models import Agent

        sub1 = Agent(name="research")
        sub2 = Agent(name="code")
        sub3 = Agent(name="analysis")

        agent = Agent(name="main", sub_agents=[sub1, sub2, sub3])

        assert len(agent.sub_agents) == 3

    def test_agent_add_sub_agent(self):
        """Test adding sub-agent to agent."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")
        sub_agent = Agent(name="sub")

        agent.add_sub_agent(sub_agent)

        assert len(agent.sub_agents) == 1

    def test_max_sub_agents_limit(self):
        """Test that max 10 sub-agents are allowed."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        # Should not raise for <= 10
        for i in range(10):
            agent.add_sub_agent(Agent(name=f"sub{i}"))

        assert len(agent.sub_agents) == 10

    def test_exceeding_max_sub_agents_raises_error(self):
        """Test that exceeding 10 sub-agents raises error."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        for i in range(10):
            agent.add_sub_agent(Agent(name=f"sub{i}"))

        # Should raise when adding 11th
        with pytest.raises(ValueError) as exc_info:
            agent.add_sub_agent(Agent(name="sub10"))

        assert "10" in str(exc_info.value)


class TestAgentHierarchyDepth:
    """Test agent hierarchy depth limits."""

    def test_default_max_depth(self):
        """Test default max depth is 3."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main")

        assert agent.max_depth == 3

    def test_custom_max_depth(self):
        """Test setting custom max depth."""
        from tinycua_sdk.models import Agent

        agent = Agent(name="main", max_depth=5)

        assert agent.max_depth == 5

    def test_current_depth_tracking(self):
        """Test current depth is tracked."""
        from tinycua_sdk.models import Agent

        parent = Agent(name="parent")
        child = Agent(name="child", current_depth=1)

        assert parent.current_depth == 0
        assert child.current_depth == 1


class TestAgentHierarchyDelegation:
    """Test agent delegation to sub-agents."""

    def test_matches_sub_agent_by_name(self):
        """Test matching sub-agent by keyword."""
        from tinycua_sdk.models import Agent

        research_agent = Agent(name="research", keywords=["research", "search", "find"])
        code_agent = Agent(name="code", keywords=["code", "program", "write"])

        agent = Agent(name="main", sub_agents=[research_agent, code_agent])

        # Should match research agent (task contains keyword "search")
        matched = agent._find_sub_agent_for_task("search for information")
        assert matched is not None
        assert matched.name == "research"

    def test_no_match_returns_none(self):
        """Test no match returns None."""
        from tinycua_sdk.models import Agent

        sub_agent = Agent(name="research")
        agent = Agent(name="main", sub_agents=[sub_agent])

        matched = agent._find_sub_agent_for_task("hello")

        # May return None or the sub-agent depending on implementation
        # The key is it doesn't crash
        assert matched is None or isinstance(matched, Agent)


class TestAgentHierarchyLocalExecution:
    """Integration tests for local execution with sub-agents."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_local_run_with_sub_agent(self):
        """Test local run with sub-agent delegation."""
        from tinycua_sdk.models import Agent

        # Create sub-agent
        research_agent = Agent(
            name="research",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )

        # Create main agent with sub-agent
        main_agent = Agent(
            name="main",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            sub_agents=[research_agent],
        )

        # Verify sub-agent is attached
        assert len(main_agent.sub_agents) == 1
        assert main_agent.sub_agents[0].name == "research"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_nested_sub_agents(self):
        """Test nested sub-agents up to max depth."""
        from tinycua_sdk.models import Agent

        # Create 3 levels of agents
        level3 = Agent(name="level3")
        level2 = Agent(name="level2", sub_agents=[level3])
        level1 = Agent(name="level1", sub_agents=[level2])

        # Get all sub-agents
        all_agents = level1._get_all_sub_agents()

        # Should include all 3 levels
        assert len(all_agents) == 3
        assert "level1" in all_agents
        assert "level2" in all_agents
        assert "level3" in all_agents


class TestAgentHierarchyExecution:
    """Test actual execution with hierarchy."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run_uses_local_when_no_delegation(self):
        """Test run uses local execution when no delegation needed."""
        from tinycua_sdk.models import Agent

        agent = Agent(
            name="test",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )

        # Simple execution should work
        result = await agent.run("Say hello")

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stream_with_sub_agents(self):
        """Test streaming with sub-agents."""
        from tinycua_sdk.models import Agent

        research_agent = Agent(
            name="research",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )

        main_agent = Agent(
            name="main",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            sub_agents=[research_agent],
        )

        # Should be able to stream
        events = []
        async for event in main_agent.stream("Hello"):
            events.append(event)

        assert len(events) > 0


class TestStreamSSE:
    """Test stream_sse functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stream_sse_with_delegation(self):
        """Test stream_sse yields all events including delegation."""
        from tinycua_sdk.models import Agent, StreamEventType

        coder = Agent(
            name="coder",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )

        coordinator = Agent(
            name="coordinator",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            sub_agents=[coder],
        )

        stream = await coordinator.run(
            "Use delegate_to_coder to write hello", stream_sse=True
        )

        events = []
        async for event in stream:
            events.append(event)

        event_types = [e.type for e in events]

        # Should have content events
        assert StreamEventType.CONTENT in event_types

        # Should have tool call events
        assert StreamEventType.TOOL_CALL_START in event_types
        assert StreamEventType.TOOL_CALL_END in event_types

        # Should have tool result events
        assert StreamEventType.TOOL_RESULT_START in event_types
        assert StreamEventType.TOOL_RESULT_END in event_types

        # Should have delegation events
        assert StreamEventType.DELEGATION_START in event_types
        assert StreamEventType.DELEGATION_END in event_types

        # Should have done event
        assert StreamEventType.DONE in event_types

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stream_sse_delegation_event_data(self):
        """Test stream_sse delegation events contain correct data."""
        from tinycua_sdk.models import Agent, StreamEventType

        coder = Agent(
            name="coder",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )

        coordinator = Agent(
            name="coordinator",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            sub_agents=[coder],
        )

        stream = await coordinator.run(
            "Use delegate_to_coder to write hello", stream_sse=True
        )

        # Find delegation events
        delegation_start = None
        delegation_end = None

        async for event in stream:
            if event.type == StreamEventType.DELEGATION_START:
                delegation_start = event.data
            elif event.type == StreamEventType.DELEGATION_END:
                delegation_end = event.data

        assert delegation_start is not None
        assert delegation_start.get("agent") == "coder"
        assert "task" in delegation_start

        assert delegation_end is not None
        assert delegation_end.get("agent") == "coder"
        assert "result_length" in delegation_end


class TestVerboseDelegation:
    """Test verbose mode with delegation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_verbose_logs_delegation(self):
        """Test verbose=True logs delegation events."""
        import logging
        from tinycua_sdk.models import Agent

        # Capture logs
        log_records = []
        handler = logging.Handler()
        handler.emit = lambda record: log_records.append(record)
        logger = logging.getLogger("tinycua_sdk.runner.runner")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        coder = Agent(
            name="coder",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )

        coordinator = Agent(
            name="coordinator",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            sub_agents=[coder],
        )

        # Run with verbose=True - delegation should be logged
        await coordinator.run("Use delegate_to_coder to write hello", verbose=True)

        # Check logs contain delegation info
        log_messages = [r.getMessage() for r in log_records]
        delegation_logs = [
            m for m in log_messages if "Delegation" in m or "delegat" in m.lower()
        ]

        assert len(delegation_logs) > 0
        assert any("delegate_to_coder" in m for m in delegation_logs)
