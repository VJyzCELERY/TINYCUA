"""Tests for AgentExecutor class."""

from tinycua_sdk.agent.config import AgentConfig
from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.llm_model import LanguageModel


class TestAgentExecutorCancel:
    """Test cancel control functionality."""

    def test_cancel_sets_flag(self):
        """Test cancel() sets cancelled flag."""
        agent = AgentExecutor(
            config=AgentConfig(llm_model=LanguageModel(model_name="gpt-4o-mini"))
        )
        assert agent.is_cancelled is False
        agent.cancel()
        assert agent.is_cancelled is True


class TestAgentExecutorConfig:
    """Test AgentExecutor config storage."""

    def test_executor_stores_config(self):
        """Test AgentExecutor keeps AgentConfig instance."""
        config = AgentConfig(llm_model=LanguageModel(model_name="gpt-4o-mini"))
        agent = AgentExecutor(config=config)
        assert agent.config is config
