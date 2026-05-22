"""Tests for provider configuration and validation."""

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.providers.utility import normalize_base_url, resolve_provider


class TestProviderResolution:
    """Tests for provider resolution and normalization."""

    def test_lmstudio_alias_resolves(self):
        """lmstudio alias should resolve to openai-compatible."""
        assert resolve_provider("lmstudio") == "openai-compatible"

    def test_ollama_alias_resolves(self):
        """ollama alias should resolve to openai-compatible."""
        assert resolve_provider("ollama") == "openai-compatible"

    def test_openai_resolves_to_openai_responses(self):
        """openai now resolves to openai-responses via new alias."""
        assert resolve_provider("openai") == "openai-responses"

    def test_case_insensitive_resolution(self):
        """Provider resolution should be case-insensitive."""
        assert resolve_provider("LMSTUDIO") == "openai-compatible"
        assert resolve_provider("Ollama") == "openai-compatible"

    def test_openai_compatible_unchanged(self):
        """openai-compatible should remain unchanged."""
        assert resolve_provider("openai-compatible") == "openai-compatible"


class TestBaseUrlNormalization:
    """Tests for base URL normalization."""

    def test_normalize_base_url_with_v1(self):
        """URL with /v1 should stay the same."""
        assert (
            normalize_base_url("http://localhost:1234/v1") == "http://localhost:1234/v1"
        )

    def test_normalize_base_url_strips_trailing_slash(self):
        """Trailing slash should be stripped."""
        assert (
            normalize_base_url("http://localhost:1234/v1/")
            == "http://localhost:1234/v1"
        )

    def test_normalize_base_url_multiple_trailing_slashes(self):
        """Multiple trailing slashes should all be stripped."""
        assert (
            normalize_base_url("http://localhost:1234/v1///")
            == "http://localhost:1234/v1"
        )

    def test_normalize_base_url_empty_string(self):
        """Empty string should remain empty (pure normalizer)."""
        assert normalize_base_url("") == ""


class TestProviderDefaults:
    """Tests for default provider configuration."""

    def test_default_provider_is_openai_responses(self):
        """Default provider should be openai-responses (from LanguageModel default)."""
        config = AgentConfig(name="test", llm_model=LanguageModel())
        assert config.llm_model.provider == "openai-responses"

    def test_provider_can_be_changed(self):
        """Provider can be changed to openai-responses."""
        config = AgentConfig(
            name="test", llm_model=LanguageModel(provider="openai-responses")
        )
        assert config.llm_model.provider == "openai-responses"

    def test_provider_with_base_url(self):
        """Provider can be configured with custom base URL."""
        config = AgentConfig(
            name="test",
            llm_model=LanguageModel(provider="openai-responses", base_url="http://localhost:8000"),
        )
        assert config.llm_model.base_url == "http://localhost:8000"


class TestProviderConfiguration:
    """Tests for provider-specific configurations."""

    def test_openai_responses_provider_config(self):
        """openai-responses provider configuration."""
        config = AgentConfig(
            name="test",
            llm_model=LanguageModel(provider="openai-responses"),
        )
        assert config.llm_model.provider == "openai-responses"


class TestProviderValidationIntegration:
    """Integration tests for provider validation."""

    def test_full_agent_config_with_provider(self):
        """Full agent config with all provider options."""
        policy = AgentPolicy(
            max_tool_calls=5,
        )
        config = AgentConfig(
            name="full-agent",
            llm_model=LanguageModel(provider="openai-responses", model_name="gpt-4o"),
            policy=policy,
        )
        assert config.llm_model.provider == "openai-responses"
        assert config.llm_model.model_name == "gpt-4o"
        assert config.policy.max_tool_calls == 5
