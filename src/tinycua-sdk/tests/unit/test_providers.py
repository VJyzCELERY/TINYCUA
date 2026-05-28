"""Tests for provider configuration and validation."""

import pytest
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.validator import AgentConfigValidator


class TestProviderValidation:
    """Tests for provider validation in agent config."""

    def test_known_provider_valid(self):
        """Known providers should not produce errors."""
        config = AgentConfig(name="test", provider="openai")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 0

    def test_ollama_provider_valid(self):
        """Ollama provider should be valid."""
        config = AgentConfig(name="test", provider="ollama")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 0

    def test_anthropic_provider_valid(self):
        """Anthropic provider should be valid."""
        config = AgentConfig(name="test", provider="anthropic")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 0

    def test_google_provider_valid(self):
        """Google provider should be valid."""
        config = AgentConfig(name="test", provider="google")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 0

    def test_local_provider_valid(self):
        """Local provider should be valid."""
        config = AgentConfig(name="test", provider="local")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 0

    def test_unknown_provider_warns(self):
        """Unknown provider should produce a warning."""
        config = AgentConfig(name="test", provider="unknown_provider")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 1
        assert provider_errors[0].severity.value == "warning"

    def test_provider_case_sensitive(self):
        """Provider names are case-sensitive (uppercase produces warning)."""
        config = AgentConfig(name="test", provider="OPENAI")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 1
        assert provider_errors[0].severity.value == "warning"


class TestProviderDefaults:
    """Tests for default provider configuration."""

    def test_default_provider_is_openai(self):
        """Default provider should be openai."""
        config = AgentConfig(name="test")
        assert config.provider == "openai"

    def test_provider_can_be_changed(self):
        """Provider can be changed to another valid provider."""
        config = AgentConfig(name="test", provider="ollama")
        assert config.provider == "ollama"

    def test_provider_with_base_url(self):
        """Provider can be configured with custom base URL."""
        config = AgentConfig(
            name="test",
            provider="local",
            base_url="http://localhost:8000",
        )
        assert config.base_url == "http://localhost:8000"


class TestProviderConfiguration:
    """Tests for provider-specific configurations."""

    def test_lmstudio_provider_config(self):
        """LMStudio provider configuration."""
        config = AgentConfig(
            name="test",
            provider="local",
        )
        assert config.provider == "local"

    def test_ollama_provider_config(self):
        """Ollama provider configuration."""
        config = AgentConfig(
            name="test",
            provider="ollama",
        )
        assert config.provider == "ollama"

    def test_anthropic_provider_config(self):
        """Anthropic provider configuration."""
        config = AgentConfig(
            name="test",
            provider="anthropic",
        )
        assert config.provider == "anthropic"

    def test_google_provider_config(self):
        """Google provider configuration."""
        config = AgentConfig(
            name="test",
            provider="google",
        )
        assert config.provider == "google"


class TestProviderValidationIntegration:
    """Integration tests for provider validation."""

    def test_full_agent_config_with_provider(self):
        """Full agent config with all provider options."""
        policy = AgentPolicy(
            max_tool_calls=5,
        )
        config = AgentConfig(
            name="full-agent",
            provider="openai",
            model="gpt-4o",
            policy=policy,
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.policy.max_tool_calls == 5

    def test_validator_with_complete_config(self):
        """Validator with complete provider configuration."""
        config = AgentConfig(
            name="complete-agent",
            provider="anthropic",
            model="claude-3-opus",
        )
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        assert len(errors) == 0
