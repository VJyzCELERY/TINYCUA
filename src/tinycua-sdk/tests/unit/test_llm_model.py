"""Tests for LanguageModel value object."""

import pytest


class TestLanguageModel:
    """Tests for LanguageModel."""

    def test_language_model_defaults(self):
        """LanguageModel has sensible defaults."""
        from tinycua_sdk import LanguageModel

        llm = LanguageModel(model_name="gpt-4o-mini")
        assert llm.provider == "openai-responses"
        assert llm.model_name == "gpt-4o-mini"
        assert llm.max_context == 128_000
        assert llm.temperature == 1.0
        assert llm.system_prompt == "You are a helpful assistant."

    def test_language_model_custom_values(self):
        """LanguageModel accepts custom values."""
        from tinycua_sdk import LanguageModel

        llm = LanguageModel(
            provider="openai-responses",
            model_name="gpt-4",
            base_url="http://localhost:1234/v1",
            max_context=64_000,
            temperature=0.5,
            system_prompt="You are a coder.",
        )
        assert llm.provider == "openai-responses"
        assert llm.model_name == "gpt-4"
        assert llm.base_url == "http://localhost:1234/v1"
        assert llm.max_context == 64_000
        assert llm.temperature == 0.5
        assert llm.system_prompt == "You are a coder."

    def test_language_model_to_dict(self):
        """LanguageModel.to_dict() returns a plain dict."""
        from tinycua_sdk import LanguageModel

        llm = LanguageModel(model_name="gpt-4")
        d = llm.to_dict()
        assert d["model_name"] == "gpt-4"
        assert "provider" in d

    def test_language_model_from_dict(self):
        """LanguageModel.from_dict() reconstructs the model."""
        from tinycua_sdk import LanguageModel

        d = {"model_name": "gpt-4", "provider": "openai-responses"}
        llm = LanguageModel.from_dict(d)
        assert llm.model_name == "gpt-4"
        assert llm.provider == "openai-responses"

    def test_language_model_immutable(self):
        """LanguageModel is immutable after creation."""
        from tinycua_sdk import LanguageModel

        llm = LanguageModel()
        with pytest.raises(Exception):
            llm.model_name = "custom"

    def test_language_model_no_io_methods(self):
        """LanguageModel has no save/load methods."""
        from tinycua_sdk import LanguageModel

        llm = LanguageModel()
        assert not hasattr(llm, "save")
        assert not hasattr(llm, "load")

    def test_language_model_round_trip(self):
        """LanguageModel serializes and deserializes correctly."""
        from tinycua_sdk import LanguageModel

        original = LanguageModel(model_name="gpt-4", temperature=0.5)
        d = original.to_dict()
        restored = LanguageModel.from_dict(d)
        assert restored.model_name == "gpt-4"
        assert restored.temperature == 0.5

    def test_system_prompt_on_language_model(self):
        """LanguageModel carries the system_prompt field."""
        from tinycua_sdk import LanguageModel

        llm = LanguageModel(system_prompt="You are a coding assistant.")
        assert llm.system_prompt == "You are a coding assistant."

    def test_model_name_resolves_provider_env_var(self, monkeypatch):
        """Empty model_name resolves from provider-specific env var."""
        from tinycua_sdk import LanguageModel

        monkeypatch.setenv("OPENAI_RESPONSES_MODEL", "env-model")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        llm = LanguageModel()
        assert llm.model_name == "env-model"

    def test_model_name_falls_back_llm_model(self, monkeypatch):
        """Empty model_name falls back to LLM_MODEL when no provider env var."""
        from tinycua_sdk import LanguageModel

        monkeypatch.delenv("OPENAI_RESPONSES_MODEL", raising=False)
        monkeypatch.setenv("LLM_MODEL", "llm-fallback")
        llm = LanguageModel()
        assert llm.model_name == "llm-fallback"

    def test_model_name_explicit_overrides_env(self, monkeypatch):
        """Explicit model_name takes precedence over env vars."""
        from tinycua_sdk import LanguageModel

        monkeypatch.setenv("OPENAI_RESPONSES_MODEL", "env-model")
        monkeypatch.setenv("LLM_MODEL", "llm-fallback")
        llm = LanguageModel(model_name="explicit-model")
        assert llm.model_name == "explicit-model"

    def test_model_name_hardcoded_default(self, monkeypatch):
        """Empty model_name with no env vars falls back to hardcoded default."""
        from tinycua_sdk import LanguageModel

        monkeypatch.delenv("OPENAI_RESPONSES_MODEL", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        llm = LanguageModel()
        assert llm.model_name == "gpt-4o-mini"

    def test_model_name_chat_completions_provider_env(self, monkeypatch):
        """Chat Completions provider resolves from its own env var."""
        from tinycua_sdk import LanguageModel

        monkeypatch.setenv("OPENAI_CHAT_COMPLETIONS_MODEL", "chat-model")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        llm = LanguageModel(provider="openai-chat-completions")
        assert llm.model_name == "chat-model"
