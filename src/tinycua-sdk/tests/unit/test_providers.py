"""Tests for provider configuration and validation."""

import pytest
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.validator import AgentConfigValidator
from tinycua_sdk.core.providers import (
    OPENAI_COMPATIBLE,
    DEFAULT_BASE_URL,
    VALID_PROVIDERS,
    resolve_provider,
    normalize_base_url,
)


class TestProviderResolution:
    """Tests for provider resolution and normalization."""

    def test_lmstudio_alias_resolves(self):
        """lmstudio alias should resolve to openai-compatible."""
        assert resolve_provider("lmstudio") == "openai-compatible"

    def test_ollama_alias_resolves(self):
        """ollama alias should resolve to openai-compatible."""
        assert resolve_provider("ollama") == "openai-compatible"

    def test_openai_remains_openai(self):
        """openai provider should remain openai."""
        assert resolve_provider("openai") == "openai"

    def test_case_insensitive_resolution(self):
        """Provider resolution should be case-insensitive."""
        assert resolve_provider("LMSTUDIO") == "openai-compatible"
        assert resolve_provider("Ollama") == "openai-compatible"
        assert resolve_provider("OpenAI") == "openai"

    def test_openai_compatible_unchanged(self):
        """openai-compatible should remain unchanged."""
        assert resolve_provider("openai-compatible") == "openai-compatible"


class TestBaseUrlNormalization:
    """Tests for base URL normalization."""

    def test_normalize_base_url_default(self):
        """None should return DEFAULT_BASE_URL."""
        assert normalize_base_url(None) == DEFAULT_BASE_URL

    def test_normalize_base_url_with_v1(self):
        """URL with /v1 should stay the same."""
        assert normalize_base_url("http://localhost:1234/v1") == "http://localhost:1234/v1"

    def test_normalize_base_url_strips_trailing_slash(self):
        """Trailing slash should be stripped."""
        assert normalize_base_url("http://localhost:1234/v1/") == "http://localhost:1234/v1"

    def test_normalize_base_url_empty_string(self):
        """Empty string should return DEFAULT_BASE_URL."""
        assert normalize_base_url("") == DEFAULT_BASE_URL


class TestProviderValidation:
    """Tests for provider validation in agent config."""

    def test_known_provider_valid(self):
        """Known providers should not produce errors."""
        config = AgentConfig(name="test", provider="openai")
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        provider_errors = [e for e in errors if e.field == "provider"]
        assert len(provider_errors) == 0

    def test_openai_compatible_provider_valid(self):
        """openai-compatible provider should be valid."""
        config = AgentConfig(name="test", provider="openai-compatible")
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
        config = AgentConfig(name="test", provider="openai-compatible")
        assert config.provider == "openai-compatible"

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

    def test_openai_compatible_provider_config(self):
        """openai-compatible provider configuration."""
        config = AgentConfig(
            name="test",
            provider="openai-compatible",
        )
        assert config.provider == "openai-compatible"

    def test_openai_provider_config(self):
        """OpenAI provider configuration."""
        config = AgentConfig(
            name="test",
            provider="openai",
        )
        assert config.provider == "openai"

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
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
        )
        validator = AgentConfigValidator()
        errors = validator.validate(config)
        assert len(errors) == 0
