"""Tests for default agent factory."""

from unittest.mock import MagicMock, patch



class TestCreateDefaultAgent:
    """Test create_default_agent() factory function."""

    def test_create_default_agent_with_defaults(self):
        """Test default agent has correct Ollama settings."""
        from tinycua.config.user_config import UserConfig
        from tinycua.agent.default_agent import create_default_agent

        mock_sdk_config = MagicMock()
        mock_sdk_config.llm.provider = "ollama"
        mock_sdk_config.llm.model = "llama3"
        mock_sdk_config.llm.base_url = "http://localhost:11434"
        mock_sdk_config.llm.api_key.get_secret_value.return_value = ""

        with patch.object(UserConfig, "load", return_value=mock_sdk_config):
            agent = create_default_agent()

        assert agent.name == "assistant"
        assert agent.config.provider == "ollama"
        assert agent.config.model == "llama3"
        assert agent.config.base_url == "http://localhost:11434"

    def test_create_default_agent_has_tools(self):
        """Test default agent includes memory and context tools."""
        from tinycua.config.user_config import UserConfig
        from tinycua.agent.default_agent import create_default_agent

        mock_sdk_config = MagicMock()
        mock_sdk_config.llm.provider = "ollama"
        mock_sdk_config.llm.model = "llama3"
        mock_sdk_config.llm.base_url = "http://localhost:11434"
        mock_sdk_config.llm.api_key.get_secret_value.return_value = ""

        with patch.object(UserConfig, "load", return_value=mock_sdk_config):
            agent = create_default_agent()

        assert len(agent.config.tools) >= 8

    def test_create_default_agent_with_custom_config(self):
        """Test default agent respects custom config."""
        from tinycua.agent.default_agent import create_default_agent

        mock_sdk_config = MagicMock()
        mock_sdk_config.llm.provider = "openai"
        mock_sdk_config.llm.model = "gpt-4"
        mock_sdk_config.llm.base_url = "https://api.openai.com/v1"
        mock_sdk_config.llm.api_key.get_secret_value.return_value = "sk-test"

        agent = create_default_agent(config=mock_sdk_config)

        assert agent.config.provider == "openai"
        assert agent.config.model == "gpt-4"
        assert agent.config.base_url == "https://api.openai.com/v1"

    def test_create_default_agent_with_custom_tools(self):
        """Test default agent accepts custom tool list."""
        from tinycua.agent.default_agent import create_default_agent

        mock_sdk_config = MagicMock()
        mock_sdk_config.llm.provider = "ollama"
        mock_sdk_config.llm.model = "llama3"
        mock_sdk_config.llm.base_url = "http://localhost:11434"
        mock_sdk_config.llm.api_key.get_secret_value.return_value = ""

        mock_tool = MagicMock()
        mock_tool.name = "custom_tool"

        agent = create_default_agent(config=mock_sdk_config, tools=[mock_tool])

        assert len(agent.config.tools) == 1
        assert agent.config.tools[0].name == "custom_tool"

    def test_create_default_agent_mode_is_local(self):
        """Test default agent starts in local mode."""
        from tinycua.config.user_config import UserConfig
        from tinycua.agent.default_agent import create_default_agent

        mock_sdk_config = MagicMock()
        mock_sdk_config.llm.provider = "ollama"
        mock_sdk_config.llm.model = "llama3"
        mock_sdk_config.llm.base_url = "http://localhost:11434"
        mock_sdk_config.llm.api_key.get_secret_value.return_value = ""

        with patch.object(UserConfig, "load", return_value=mock_sdk_config):
            agent = create_default_agent()

        assert agent.config.mode == "local"

    def test_create_default_agent_fallback_on_config_error(self):
        """Test default agent falls back to SDKConfig if UserConfig fails."""
        from tinycua.agent.default_agent import create_default_agent

        with patch("tinycua.config.user_config.UserConfig") as mock_user_config:
            mock_user_config.load.side_effect = Exception("Config error")

            agent = create_default_agent()

        assert agent is not None
        assert agent.config.provider == "lmstudio"
