"""Provider registry — maps provider identifiers to client factories.

Extracted from ``core/providers.py`` — the ``ProviderRegistry`` manages
provider lifecycle decisions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tinycua_sdk.agent.llm_client import LLMClient
    from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua_sdk.core.exceptions import ProviderNotSupportedError
from tinycua_sdk.providers.constants import OPENAI_CHAT_COMPLETIONS, OPENAI_RESPONSES
from tinycua_sdk.providers.utility import (
    ProviderFactory,
    ProviderInfo,
    resolve_provider,
)

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Maps provider identifiers to client factories.

    Supports registration, client creation, listing, and reset for testing.
    Provider support/rejection is owned by this registry — unrecognized
    providers raise ``ProviderNotSupportedError`` at ``create_client()`` time.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderInfo] = {}

    def register(
        self,
        provider_id: str,
        factory: ProviderFactory,
        metadata: ProviderInfo | None = None,
    ) -> None:
        """Register a provider factory with metadata.

        The ``provider_id`` is normalized via ``resolve_provider()`` to
        its canonical form (e.g., ``"lmstudio"`` → ``"openai-compatible"``)
        so that alias-based registration is consistent with the public
        ``LanguageModel`` resolution path.

        The explicit ``factory`` argument takes precedence over
        ``metadata.factory``. If they differ, ``metadata`` is copied
        with its factory replaced by the explicit argument.

        The explicit ``provider_id`` takes precedence over
        ``metadata.id``. If they differ, a ``ValueError`` is raised
        to prevent silent id mismatch.

        When ``metadata`` is None, a default ``ProviderInfo`` is
        synthesized using the given ``provider_id``, ``factory``,
        and an empty description.

        Args:
            provider_id: Unique provider identifier (may be an alias).
            factory: Callable that creates an ``LLMClient`` from a
                ``LanguageModel`` configuration.
            metadata: Optional ``ProviderInfo`` instance with provider metadata.

        Raises:
            ValueError: If ``metadata.id`` differs from ``provider_id``.
        """
        from dataclasses import replace

        provider_id = resolve_provider(provider_id)
        if metadata is not None:
            metadata = replace(metadata, id=resolve_provider(metadata.id))
        if metadata is None:
            metadata = ProviderInfo(id=provider_id, factory=factory, description="")
        if metadata.id != provider_id:
            raise ValueError(
                f"metadata.id ({metadata.id!r}) conflicts with provider_id ({provider_id!r})"
            )

        self._providers[provider_id] = replace(metadata, id=provider_id, factory=factory)

    def create_client(
        self,
        model_config: LanguageModel,
        upload_session: Any = None,
    ) -> LLMClient:
        """Create an ``LLMClient`` for the given model configuration.

        Args:
            model_config: Language model configuration with ``provider``
                field identifying the desired provider.
            upload_session: Optional ``UploadSession`` for file upload caching.

        Returns:
            An ``LLMClient`` instance configured for the provider.

        Raises:
            ProviderNotSupportedError: If the provider is not registered.
        """
        provider_id = resolve_provider(model_config.provider)
        info = self._providers.get(provider_id)
        if info is None:
            supported = list(self._providers.keys())
            raise ProviderNotSupportedError(provider_id, supported)
        return info.factory(model_config, upload_session=upload_session)

    def list_providers(self) -> list[ProviderInfo]:
        """List all registered providers.

        Returns:
            List of ``ProviderInfo`` for all registered providers.
        """
        return list(self._providers.values())

    def is_supported(self, provider_id: str) -> bool:
        """Check if a provider is registered.

        The ``provider_id`` is normalized via ``resolve_provider()``
        before lookup, so alias identifiers resolve to the canonical key.

        Args:
            provider_id: Provider identifier to check (may be an alias).

        Returns:
            True if the provider is registered.
        """
        return resolve_provider(provider_id) in self._providers

    def reset(self) -> None:
        """Clear all registered providers.

        Used primarily in testing to get a clean registry state.
        """
        self._providers.clear()


# ── Singleton Registry ──────────────────────────────────────────────────────

_provider_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Return the singleton ``ProviderRegistry`` instance.

    Lazily initializes the registry on first call and registers
    default providers (``openai-responses`` → ``OpenAIResponsesClient``,
    ``openai-chat-completions`` → ``OpenAIChatCompletionsClient``).

    Returns:
        The singleton ``ProviderRegistry`` instance.
    """
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
        _register_defaults(_provider_registry)
    return _provider_registry


def _register_defaults(registry: ProviderRegistry) -> None:
    """Register default Phase 1 providers in the given registry.

    Args:
        registry: The ``ProviderRegistry`` to register defaults in.
    """

    def _openai_responses_factory(model_config: LanguageModel, upload_session: Any = None) -> Any:
        from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient  # noqa: PLC0415

        return OpenAIResponsesClient(model_config, upload_session=upload_session)

    registry.register(
        OPENAI_RESPONSES,
        _openai_responses_factory,
        ProviderInfo(
            id=OPENAI_RESPONSES,
            factory=_openai_responses_factory,
            description="OpenAI Responses API",
        ),
    )

    def _openai_chat_completions_factory(model_config: LanguageModel, upload_session: Any = None) -> Any:
        from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient  # noqa: PLC0415

        return OpenAIChatCompletionsClient(model_config, upload_session=upload_session)

    registry.register(
        OPENAI_CHAT_COMPLETIONS,
        _openai_chat_completions_factory,
        ProviderInfo(
            id=OPENAI_CHAT_COMPLETIONS,
            factory=_openai_chat_completions_factory,
            description="OpenAI Chat Completions API",
        ),
    )


__all__ = [
    "ProviderRegistry",
    "get_provider_registry",
]
