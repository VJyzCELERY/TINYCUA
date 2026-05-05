"""Tests for AgentExecutor class."""

import asyncio


from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_model import LanguageModel


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
            llm_model=LanguageModel(model_name="gpt-4o-mini"),
        )

        assert agent.name == "test"
        assert agent.instructions == "test instructions"
        assert agent.model == "gpt-4o-mini"

    def test_executor_has_tools_list(self):
        """Test AgentExecutor has tools list."""
        agent = AgentExecutor(name="test")
        assert isinstance(agent.tools, list)
        assert len(agent.tools) == 0
