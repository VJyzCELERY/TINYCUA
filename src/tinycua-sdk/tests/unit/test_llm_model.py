"""Tests for LLMModel value object."""

import pytest


class TestLLMModel:
    """Tests for LLMModel."""

    def test_llm_model_defaults(self):
        """LLMModel has sensible defaults."""
        from tinycua_sdk import LLMModel

        llm = LLMModel()
        assert llm.provider == "openai-compatible"
        assert llm.model_name == "gpt-4o-mini"
        assert llm.max_context == 128_000
        assert llm.temperature == 1.0
        assert llm.system_prompt == "You are a helpful assistant."

    def test_llm_model_custom_values(self):
        """LLMModel accepts custom values."""
        from tinycua_sdk import LLMModel

        llm = LLMModel(
            provider="openai",
            model_name="gpt-4",
            base_url="http://localhost:1234/v1",
            max_context=64_000,
            temperature=0.5,
            system_prompt="You are a coder.",
        )
        assert llm.provider == "openai"
        assert llm.model_name == "gpt-4"
        assert llm.base_url == "http://localhost:1234/v1"
        assert llm.max_context == 64_000
        assert llm.temperature == 0.5
        assert llm.system_prompt == "You are a coder."

    def test_llm_model_to_dict(self):
        """LLMModel.to_dict() returns a plain dict."""
        from tinycua_sdk import LLMModel

        llm = LLMModel(model_name="gpt-4")
        d = llm.to_dict()
        assert d["model_name"] == "gpt-4"
        assert "provider" in d

    def test_llm_model_from_dict(self):
        """LLMModel.from_dict() reconstructs the model."""
        from tinycua_sdk import LLMModel

        d = {"model_name": "gpt-4", "provider": "openai"}
        llm = LLMModel.from_dict(d)
        assert llm.model_name == "gpt-4"
        assert llm.provider == "openai"

    def test_llm_model_immutable(self):
        """LLMModel is immutable after creation."""
        from tinycua_sdk import LLMModel

        llm = LLMModel()
        with pytest.raises(Exception):
            llm.model_name = "custom"

    def test_llm_model_no_io_methods(self):
        """LLMModel has no save/load methods."""
        from tinycua_sdk import LLMModel

        llm = LLMModel()
        assert not hasattr(llm, "save")
        assert not hasattr(llm, "load")

    def test_llm_model_round_trip(self):
        """LLMModel serializes and deserializes correctly."""
        from tinycua_sdk import LLMModel

        original = LLMModel(model_name="gpt-4", temperature=0.5)
        d = original.to_dict()
        restored = LLMModel.from_dict(d)
        assert restored.model_name == "gpt-4"
        assert restored.temperature == 0.5

    def test_system_prompt_on_llm_model(self):
        """LLMModel carries the system_prompt field."""
        from tinycua_sdk import LLMModel

        llm = LLMModel(system_prompt="You are a coding assistant.")
        assert llm.system_prompt == "You are a coding assistant."
