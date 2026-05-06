"""Tests for provider configuration and validation."""

import pytest
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.llm_model import LanguageModel
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


class TestProviderDefaults:
    """Tests for default provider configuration."""

    def test_default_provider_is_openai_compatible(self):
        """Default provider should be openai-compatible."""
        config = AgentConfig(name="test")
        assert config.llm_model.provider == "openai-compatible"

    def test_provider_can_be_changed(self):
        """Provider can be changed to another valid provider."""
        config = AgentConfig(name="test", llm_model=LanguageModel(provider="openai-compatible"))
        assert config.llm_model.provider == "openai-compatible"

    def test_provider_with_base_url(self):
        """Provider can be configured with custom base URL."""
        config = AgentConfig(
            name="test",
            llm_model=LanguageModel(provider="local", base_url="http://localhost:8000"),
        )
        assert config.llm_model.base_url == "http://localhost:8000"


class TestProviderConfiguration:
    """Tests for provider-specific configurations."""

    def test_openai_compatible_provider_config(self):
        """openai-compatible provider configuration."""
        config = AgentConfig(
            name="test",
            llm_model=LanguageModel(provider="openai-compatible"),
        )
        assert config.llm_model.provider == "openai-compatible"

    def test_openai_provider_config(self):
        """OpenAI provider configuration."""
        config = AgentConfig(
            name="test",
            llm_model=LanguageModel(provider="openai"),
        )
        assert config.llm_model.provider == "openai"


class TestProviderValidationIntegration:
    """Integration tests for provider validation."""

    def test_full_agent_config_with_provider(self):
        """Full agent config with all provider options."""
        policy = AgentPolicy(
            max_tool_calls=5,
        )
        config = AgentConfig(
            name="full-agent",
            llm_model=LanguageModel(provider="openai", model_name="gpt-4o"),
            policy=policy,
        )
        assert config.llm_model.provider == "openai"
        assert config.llm_model.model_name == "gpt-4o"
        assert config.policy.max_tool_calls == 5
