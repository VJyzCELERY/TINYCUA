"""Tests for import sanity — verifying new provider import paths resolve correctly."""


class TestNewProviderImports:
    """Smoke tests for the new providers package structure (FR-001 through FR-004)."""

    def test_providers_package_importable(self):
        """FR-001: The providers package is importable."""
        import tinycua_sdk.providers  # noqa: F401

    def test_openai_responses_client_new_path(self):
        """FR-002/AC-001: OpenAIResponsesClient importable from providers."""
        from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

        assert OpenAIResponsesClient is not None

    def test_openai_chat_completions_client_new_path(self):
        """OpenAIChatCompletionsClient importable from providers."""
        from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient

        assert OpenAIChatCompletionsClient is not None

    def test_provider_utilities_new_path(self):
        """FR-004/AC-004: resolve_provider, normalize_base_url from providers.utility."""
        from tinycua_sdk.providers.utility import normalize_base_url, resolve_provider

        assert callable(resolve_provider)
        assert callable(normalize_base_url)

    def test_provider_registry_new_path(self):
        """FR-004: ProviderRegistry importable from providers.registry."""
        from tinycua_sdk.providers.registry import ProviderRegistry

        assert ProviderRegistry is not None

    def test_convenience_namespace(self):
        """AC-004: Convenience re-exports via tinycua_sdk.providers."""
        from tinycua_sdk.providers import (
            resolve_provider,
        )

        assert callable(resolve_provider)

    def test_llm_client_abc_still_in_agent(self):
        """AC-003: LLMClient ABC still resolves from agent.llm_client."""
        from tinycua_sdk.agent.llm_client import LLMClient

        assert LLMClient is not None
