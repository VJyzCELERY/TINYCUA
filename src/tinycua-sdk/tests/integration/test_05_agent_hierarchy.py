"""Integration Tests: Agent Hierarchy and Delegation

Tests based on example: 05_agent_hierarchy.py
Tests:
1. Agent hierarchy structure
2. Manual delegation
3. LLM-based delegation
4. Streaming with delegation
"""

import pytest
import logging
from tinycua_sdk.agent import Agent

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def hierarchical_agents():
    """Create a hierarchy of agents."""
    researcher = Agent(
        name="researcher",
        instructions="You are a research assistant.",
    )
    coder = Agent(
        name="coder",
        instructions="You are a coding assistant.",
    )
    writer = Agent(
        name="writer",
        instructions="You are a technical writer.",
    )

    coordinator = Agent(
        name="coordinator",
        instructions="You coordinate tasks between agents.",
        sub_agents=[researcher, coder, writer],
    )

    return coordinator, [researcher, coder, writer]


# =============================================================================
# Test Cases
# =============================================================================

class TestAgentHierarchy:
    """Test agent hierarchy structure."""

    def test_create_sub_agents(self, hierarchical_agents):
        """Test creating sub-agents."""
        logger.info("Testing sub-agent creation")
        _, sub_agents = hierarchical_agents
        logger.info(f"Created {len(sub_agents)} sub-agents: {[a.name for a in sub_agents]}")
        assert len(sub_agents) == 3

    def test_main_agent_has_sub_agents(self, hierarchical_agents):
        """Test that main agent has sub-agents."""
        logger.info("Testing main agent has sub-agents")
        main_agent, _ = hierarchical_agents
        logger.info(f"Main agent sub-agents: {[a.name for a in main_agent.sub_agents]}")
        assert len(main_agent.sub_agents) == 3

    def test_sub_agent_names(self, hierarchical_agents):
        """Test sub-agent names."""
        logger.info("Testing sub-agent names")
        main_agent, sub_agents = hierarchical_agents
        names = [a.name for a in sub_agents]
        logger.info(f"Sub-agent names: {names}")
        assert "researcher" in names
        assert "coder" in names
        assert "writer" in names


class TestManualDelegation:
    """Test manual delegation."""

    def test_pass_context_to_sub_agent(self, hierarchical_agents):
        """Test passing context to sub-agent."""
        logger.info("Testing _pass_context_to_sub_agent")
        main_agent, _ = hierarchical_agents
        sub_agent = main_agent.sub_agents[0]

        context = main_agent._pass_context_to_sub_agent("Hello", sub_agent)
        logger.info(f"Context passed: {len(context)} chars")
        assert isinstance(context, str)
        assert len(context) > 0

    def test_aggregate_results(self, hierarchical_agents):
        """Test aggregating results from sub-agents."""
        logger.info("Testing _aggregate_results")
        main_agent, _ = hierarchical_agents
        sub_agent = main_agent.sub_agents[0]

        result = main_agent._aggregate_results("Test result", sub_agent)
        logger.info(f"Result aggregated: {len(result)} chars")
        assert isinstance(result, str)


class TestAgentConfiguration:
    """Test agent configuration."""

    def test_agent_with_sub_agents(self):
        """Test agent with sub-agents."""
        sub_agent = Agent(name="sub", instructions="Sub agent.")
        main_agent = Agent(
            name="main",
            instructions="Main agent.",
            sub_agents=[sub_agent],
        )

        assert len(main_agent.sub_agents) == 1
        assert main_agent.sub_agents[0].name == "sub"

    def test_agent_without_sub_agents(self):
        """Test agent without sub-agents."""
        agent = Agent(name="agent", instructions="Agent.")
        assert len(agent.sub_agents) == 0


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
