"""Integration tests for LanguageModel value object.

Converts targets: 01_minimal_creation, 02_full_configuration,
03_serialization_roundtrip, 04_json_export_import
"""

import os
import pytest

from tinycua_sdk import LanguageModel


# Set environment variable for env-var substitution test
os.environ["OPENAI_API_KEY"] = "test-key-from-env"


class TestGS01LanguageModelDefinition:
    """Test suite for LanguageModel creation patterns and serialization."""

    def test_gs_01_minimal_creation(self):
        """Target 1.1: Create a minimal LanguageModel with defaults."""
        m = LanguageModel(model_name="qwen/qwen3.5-9b")

        assert m.provider == "openai-compatible"
        assert m.model_name == "qwen/qwen3.5-9b"
        assert m.temperature == 1.0
        assert m.max_tokens is None

    def test_gs_02_full_configuration(self):
        """Target 1.2: Create a LanguageModel with all OpenAI-compatible params."""
        m = LanguageModel(
            provider="openai",
            model_name="gpt-4o",
            api_key="${OPENAI_API_KEY}",
            temperature=0.5,
            max_tokens=8192,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1,
            response_format={"type": "json_object"},
            system_prompt="You are terse.",
        )

        assert m.provider == "openai"
        assert m.model_name == "gpt-4o"
        assert m.temperature == 0.5
        assert m.max_tokens == 8192
        assert m.top_p == 0.9
        assert m.frequency_penalty == 0.1
        assert m.presence_penalty == 0.1
        assert m.response_format == {"type": "json_object"}

    def test_gs_03_serialization_roundtrip(self):
        """Target 1.3: Verify to_dict/from_dict round-trip preserves all data."""
        original = LanguageModel(
            model_name="test-model",
            temperature=0.3,
            max_tokens=512,
            top_p=0.8,
            frequency_penalty=0.2,
            presence_penalty=0.1,
            response_format={"type": "json_object"},
        )

        restored = LanguageModel.from_dict(original.to_dict())

        assert restored.model_name == original.model_name
        assert restored.temperature == original.temperature
        assert restored.max_tokens == original.max_tokens
        assert restored.top_p == original.top_p
        assert restored.frequency_penalty == original.frequency_penalty
        assert restored.presence_penalty == original.presence_penalty
        assert restored.response_format == original.response_format

    def test_gs_04_json_export_import(self):
        """Target 1.4: Verify to_json/from_json round-trip."""
        original = LanguageModel(
            model_name="json-test",
            temperature=0.7,
            max_tokens=256,
        )

        json_str = original.to_json()
        restored = LanguageModel.from_json(json_str)

        assert restored.model_name == original.model_name
        assert restored.temperature == original.temperature
        assert restored.max_tokens == original.max_tokens

    def test_gs_05_frozen_immutable(self):
        """Verify LanguageModel is frozen (mutation raises error)."""
        m = LanguageModel(model_name="frozen-test")
        with pytest.raises(Exception):
            m.temperature = 0.5

    def test_gs_06_env_var_substitution(self):
        """Verify env-var substitution resolves ${VAR_NAME} in api_key."""
        m = LanguageModel(
            model_name="env-test",
            api_key="${OPENAI_API_KEY}",
        )
        assert m.api_key.get_secret_value() == "test-key-from-env"

    def test_gs_07_to_dict_excludes_none(self):
        """Verify to_dict excludes None values."""
        m = LanguageModel(model_name="exclude-test")
        d = m.to_dict()
        assert "max_tokens" not in d
        assert "stop" not in d
        assert "seed" not in d

    def test_gs_08_provider_normalization(self):
        """Verify provider normalization via resolve_provider."""
        m = LanguageModel(model_name="test", provider="lmstudio")
        assert m.provider == "openai-compatible"

        m2 = LanguageModel(model_name="test", provider="ollama")
        assert m2.provider == "openai-compatible"

        m3 = LanguageModel(model_name="test", provider="openai")
        assert m3.provider == "openai"
