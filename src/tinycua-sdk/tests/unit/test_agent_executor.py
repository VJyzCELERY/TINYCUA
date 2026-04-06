"""Tests for AgentExecutor class."""

import asyncio
from unittest.mock import MagicMock, patch


from tinycua_sdk.agent.executor import AgentExecutor


class TestAgentExecutorCancel:
    """Test cancel control functionality."""

    def test_cancel_event_created_on_access(self):
        """Test cancel_event is created lazily."""
        agent = AgentExecutor(name="test")
        assert not hasattr(agent, "_cancel_event")
        event = agent.cancel_event
        assert isinstance(event, asyncio.Event)
        assert agent._cancel_event is event

    def test_cancel_sets_event(self):
        """Test cancel() sets the cancel event."""
        agent = AgentExecutor(name="test")
        agent.cancel()
        assert agent.is_cancelled is True

    def test_reset_cancel_clears_event(self):
        """Test reset_cancel() clears the cancel event."""
        agent = AgentExecutor(name="test")
        agent.cancel()
        assert agent.is_cancelled is True
        agent.reset_cancel()
        assert agent.is_cancelled is False

    def test_guest_session_id_default_none(self):
        """Test guest_session_id defaults to None."""
        agent = AgentExecutor(name="test")
        assert agent.guest_session_id is None

    def test_guest_session_id_setter(self):
        """Test guest_session_id can be set."""
        agent = AgentExecutor(name="test")
        agent.guest_session_id = "session-123"
        assert agent.guest_session_id == "session-123"


class TestAgentExecutorRunner:
    """Test runner and loop management."""

    def test_get_runner_creates_runner(self):
        """Test _get_runner() creates a Runner instance."""

        agent = AgentExecutor(name="test")
        with patch("tinycua_sdk.runner.Runner") as mock_runner:
            mock_runner.return_value = MagicMock()
            runner = agent._get_runner()

            mock_runner.assert_called_once_with(agent.config)
            assert agent._local_runner is runner

    def test_get_runner_returns_cached_runner(self):
        """Test _get_runner() returns cached runner."""
        agent = AgentExecutor(name="test")
        mock_runner = MagicMock()
        agent._local_runner = mock_runner

        with patch("tinycua_sdk.runner.Runner") as mock_runner_cls:
            runner = agent._get_runner()

            mock_runner_cls.assert_not_called()
            assert runner is mock_runner


class TestAgentExecutorInheritance:
    """Test AgentExecutor inherits from AgentDefinition."""

    def test_executor_is_definition_subclass(self):
        """Test AgentExecutor is a subclass of AgentDefinition."""
        from tinycua_sdk.agent.definition import AgentDefinition

        assert issubclass(AgentExecutor, AgentDefinition)

    def test_executor_has_all_definition_properties(self):
        """Test AgentExecutor has all AgentDefinition properties."""
        agent = AgentExecutor(
            name="test",
            instructions="test instructions",
            model="gpt-4o-mini",
        )

        assert agent.name == "test"
        assert agent.instructions == "test instructions"
        assert agent.model == "gpt-4o-mini"
        assert agent.is_deployed is False
        assert agent.is_guest is False

    def test_executor_has_messages_list(self):
        """Test AgentExecutor has messages list."""
        agent = AgentExecutor(name="test")
        assert isinstance(agent.messages, list)
        assert len(agent.messages) == 0

    def test_executor_has_loop_cache(self):
        """Test AgentExecutor has loop cache."""
        agent = AgentExecutor(name="test")
        assert agent._loop_cache is None
