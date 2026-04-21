"""Unit tests for TUI AgentManager."""

import pytest
from unittest.mock import MagicMock, patch
import uuid


class TestAgentManager:
    """Tests for AgentManager."""

    def test_agent_manager_initializes(self):
        """Test agent manager initializes correctly."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        assert manager is not None
        agents = manager.list_agents()
        assert isinstance(agents, list)

    def test_create_agent(self):
        """Test creating a new agent."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        agent = manager.create_agent(
            name="test-agent",
            model="gpt-4",
            provider="openai",
            system_prompt="You are a test assistant.",
        )

        assert agent is not None
        assert agent.name == "test-agent"
        assert agent.config.model == "gpt-4"
        assert agent.config.provider == "openai"

    def test_list_agents(self):
        """Test listing agents."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        manager.create_agent(name="agent1")
        manager.create_agent(name="agent2")

        agents = manager.list_agents()
        assert len(agents) >= 2
        names = [a.name for a in agents]
        assert "agent1" in names
        assert "agent2" in names

    def test_get_agent(self):
        """Test getting a specific agent."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        created = manager.create_agent(name="test-agent")

        assert created is not None
        retrieved = manager.get_agent(created.id)
        assert retrieved is not None
        assert retrieved.name == "test-agent"

    def test_update_agent(self):
        """Test updating an agent."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        created = manager.create_agent(name="original-name")

        assert created is not None
        updated = manager.update_agent(
            created.id, name="updated-name", model="gpt-5"
        )

        assert updated is not None
        assert updated.name == "updated-name"
        assert updated.config.model == "gpt-5"

    def test_delete_agent(self):
        """Test deleting an agent."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        created = manager.create_agent(name="to-delete")

        assert created is not None
        result = manager.delete_agent(created.id)
        assert result is True

        retrieved = manager.get_agent(created.id)
        assert retrieved is None

    def test_set_current_agent(self):
        """Test setting current agent."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        created = manager.create_agent(name="current-agent")

        assert created is not None
        result = manager.set_current_agent(created.id)
        assert result is True

        current = manager.get_current_agent()
        assert current is not None
        assert current.name == "current-agent"

    def test_init_default_agent(self):
        """Test initializing default agent via SDK."""
        from tinycua.tui.agent_manager import AgentManager

        manager = AgentManager()
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"

        with patch(
            "tinycua.agent.default_agent.create_default_agent",
            return_value=mock_agent,
        ):
            agent = manager.init_default_agent()

        assert agent is not None
        assert agent.name == "test-agent"
        assert manager.get_default_agent() is not None


class TestAgentInfo:
    """Tests for AgentInfo dataclass."""

    def test_agent_info_creation(self):
        """Test AgentInfo creation."""
        from tinycua.tui.agent_manager import AgentInfo
        from tinycua_sdk.agent.config import AgentConfig

        agent_id = uuid.uuid4()
        config = AgentConfig(name="test")
        info = AgentInfo(id=agent_id, name="test", config=config)

        assert info.id == agent_id
        assert info.name == "test"
        assert info.config.name == "test"
