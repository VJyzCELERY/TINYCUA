"""Tests for AgentLifecycle class."""

import pytest
from unittest.mock import AsyncMock, patch


class TestAgentLifecycleDeploy:
    """Test AgentLifecycle deploy functionality."""

    @pytest.mark.asyncio
    async def test_deploy_calls_backend(self):
        """Test deploy calls backend client correctly."""
        from tinycua_sdk.agent.agent import Agent
        from tinycua.agent.lifecycle import AgentLifecycle

        agent = Agent(name="test-agent")
        lifecycle = AgentLifecycle(
            agent,
            backend_url="http://localhost:8000",
            backend_api_key="test-key",
        )

        with patch.object(
            lifecycle,
            "_get_backend_config",
            return_value=("http://localhost:8000", "test-key", None),
        ):
            with patch("tinycua.agent.lifecycle.BackendClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.list_tools.return_value = []
                mock_client.deploy_agent.return_value = {
                    "id": "agent-123",
                    "status": "deployed",
                }
                mock_client_cls.return_value = mock_client

                result = await lifecycle.deploy()

                assert result["id"] == "agent-123"
                assert agent.config.mode == "deployed"
                assert agent.config.agent_id == "agent-123"


class TestAgentLifecycleDelete:
    """Test AgentLifecycle delete functionality."""

    @pytest.mark.asyncio
    async def test_delete_calls_backend(self):
        """Test delete calls backend client correctly."""
        from tinycua_sdk.agent.agent import Agent
        from tinycua.agent.lifecycle import AgentLifecycle

        agent = Agent(name="test-agent")
        agent.config.agent_id = "agent-123"
        agent.config.mode = "deployed"

        lifecycle = AgentLifecycle(
            agent,
            backend_url="http://localhost:8000",
            backend_api_key="test-key",
        )

        with patch.object(
            lifecycle,
            "_get_backend_config",
            return_value=("http://localhost:8000", "test-key", None),
        ):
            with patch("tinycua.agent.lifecycle.BackendClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.delete_agent = AsyncMock()
                mock_client_cls.return_value = mock_client

                await lifecycle.delete()

                mock_client.delete_agent.assert_called_once_with(agent_id="agent-123")
                assert agent.config.agent_id is None
                assert agent.config.mode == "local"

    @pytest.mark.asyncio
    async def test_delete_raises_when_not_deployed(self):
        """Test delete raises RuntimeError when agent is not deployed."""
        from tinycua_sdk.agent.agent import Agent
        from tinycua.agent.lifecycle import AgentLifecycle

        agent = Agent(name="test-agent")
        lifecycle = AgentLifecycle(agent)

        with pytest.raises(RuntimeError, match="Agent not deployed"):
            await lifecycle.delete()


class TestAgentLifecycleGuestMode:
    """Test AgentLifecycle guest mode functionality."""

    def test_set_guest_mode(self):
        """Test set_guest_mode updates agent config."""
        from tinycua_sdk.agent.agent import Agent
        from tinycua.agent.lifecycle import AgentLifecycle

        agent = Agent(name="test-agent")
        lifecycle = AgentLifecycle(agent)

        lifecycle.set_guest_mode("agent-123", backend_url="http://test:8000")

        assert agent.config.mode == "guest"
        assert agent.config.agent_id == "agent-123"
        assert agent.config.backend_url == "http://test:8000"


class TestAgentLifecycleLoadAgent:
    """Test AgentLifecycle load_agent functionality."""

    @pytest.mark.asyncio
    async def test_load_agent(self):
        """Test load_agent creates agent from backend config."""
        from tinycua.agent.lifecycle import AgentLifecycle

        with patch("tinycua.agent.lifecycle.BackendClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_agent.return_value = {
                "name": "loaded-agent",
                "instructions": "Loaded instructions",
                "model": "gpt-4o-mini",
                "provider": "openai",
            }
            mock_client_cls.return_value = mock_client

            agent = await AgentLifecycle.load_agent(
                agent_id="agent-123",
                backend_url="http://localhost:8000",
            )

            assert agent.name == "loaded-agent"
            assert agent.config.agent_id == "agent-123"
            assert agent.config.mode == "deployed"
            assert agent.config.backend_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_load_agent_reuses_client(self):
        """Test load_agent reuses a passed-in client."""
        from tinycua.agent.lifecycle import AgentLifecycle

        mock_client = AsyncMock()
        mock_client.get_agent.return_value = {
            "name": "reused-agent",
            "instructions": "Reused instructions",
            "model": "gpt-4o-mini",
            "provider": "openai",
        }

        with patch("tinycua.agent.lifecycle.BackendClient") as mock_client_cls:
            agent = await AgentLifecycle.load_agent(
                agent_id="agent-456",
                backend_url="http://localhost:8000",
                client=mock_client,
            )

            assert agent.name == "reused-agent"
            mock_client_cls.assert_not_called()
            mock_client.get_agent.assert_called_once_with("agent-456")
