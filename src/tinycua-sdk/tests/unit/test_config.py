"""Tests for config serialization and deserialization."""




class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_agent_config_defaults(self):
        """AgentConfig has sensible defaults."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert config.name == "assistant"
        assert config.instructions == ""

    def test_agent_config_to_dict(self):
        """AgentConfig.to_dict() returns a plain dict."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig(name="test")
        d = config.to_dict()
        assert d["name"] == "test"

    def test_agent_config_from_dict(self):
        """AgentConfig.from_dict() reconstructs the config."""
        from tinycua_sdk import AgentConfig

        d = {"name": "test", "instructions": "Be helpful"}
        config = AgentConfig.from_dict(d)
        assert config.name == "test"
        assert config.instructions == "Be helpful"

    def test_agent_config_no_system_prompt_field(self):
        """AgentConfig does not have a system_prompt field."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert not hasattr(config, "system_prompt")

    def test_agent_config_no_session_id_field(self):
        """AgentConfig does not have a session_id field."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert not hasattr(config, "session_id")

    def test_agent_config_no_memory_fields(self):
        """AgentConfig does not have memory fields."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert not hasattr(config, "short_term_memory")
        assert not hasattr(config, "long_term_memory")


class TestConfigRoundTrip:
    """Tests for config serialization round-trips."""

    def test_agent_config_round_trip(self):
        """AgentConfig serializes and deserializes correctly."""
        from tinycua_sdk import AgentConfig, LanguageModel

        original = AgentConfig(
            name="test",
            llm_model=LanguageModel(model_name="gpt-4"),
        )
        d = original.to_dict()
        restored = AgentConfig.from_dict(d)
        assert restored.name == "test"
        assert restored.llm_model.model_name == "gpt-4"
