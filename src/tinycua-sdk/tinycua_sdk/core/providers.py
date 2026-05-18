"""LLM provider resolution, normalization, and registry.

This module provides centralized provider resolution, URL normalization,
and the ``ProviderRegistry`` for the TINYCUA SDK. It unifies all
OpenAI-compatible endpoints under a single canonical identifier while
maintaining backward-compatible aliases.

The ``ProviderRegistry`` owns provider support/rejection — unrecognized
providers are rejected at ``create_client()`` time via
``ProviderNotSupportedError``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from tinycua_sdk.agent.llm_client import LLMClient
    from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua_sdk.core.exceptions import ProviderNotSupportedError

logger = logging.getLogger(__name__)

#: The canonical identifier for OpenAI-compatible endpoints.
OPENAI_COMPATIBLE: Final = "openai-compatible"

#: The canonical identifier for OpenAI Responses API.
OPENAI_RESPONSES: Final = "openai-responses"

#: Default base URL for local OpenAI-compatible endpoints.
DEFAULT_BASE_URL: Final = "http://localhost:1234/v1"

#: Default base URL for OpenAI Responses API.
OPENAI_BASE_URL: Final = "https://api.openai.com/v1"

#: Backward-compatible aliases that map to the canonical identifier.
_PROVIDER_ALIASES: Final[dict[str, str]] = {
    "lmstudio": OPENAI_COMPATIBLE,
    "ollama": OPENAI_COMPATIBLE,
}

#: Recognized provider identifiers (canonical + aliases + openai-responses).
#:
#: .. note::
#:     This set lists all *recognized* provider identifier strings, but only
#:     *registered* providers are functional at runtime. Registration is owned
#:     by ``ProviderRegistry`` — see ``get_provider_registry().register()``.
#:     Unregistered providers (e.g. ``"openai-compatible"``, ``"lmstudio"``)
#:     raise ``ProviderNotSupportedError`` from ``create_client()``.
#:
#:     **Phase 1** removes the old generic OpenAI-compatible registration;
#:     only ``OPENAI_RESPONSES`` (``"openai-responses"``) is registered by
#:     default. Consumers that need ``"openai-compatible"`` must register
#:     a factory explicitly.



def resolve_provider(provider: str) -> str:
    """Resolve a provider identifier to its canonical form.

    Args:
        provider: Raw provider identifier from user input.

    Returns:
        Canonical provider identifier.

    Example:
        >>> resolve_provider("lmstudio")
        'openai-compatible'
        >>> resolve_provider("openai")
        'openai'
        >>> resolve_provider("openai-responses")
        'openai-responses'

    """
    normalized = provider.lower().strip()
    canonical = _PROVIDER_ALIASES.get(normalized, normalized)
    if normalized != canonical and normalized in _PROVIDER_ALIASES:
        logger.warning(
            "Provider alias '%s' is deprecated. Use '%s' instead.",
            normalized,
            canonical,
        )
    return canonical


def normalize_base_url(url: str | None, provider: str = "openai-compatible") -> str:
    """Normalize a base URL.

    - If None/empty, returns provider-specific default.
    - Strips trailing slash to prevent double slashes.
    - Does NOT append /v1 (user must provide full URL).

    Args:
        url: Raw base URL.
        provider: Provider name for provider-specific defaults.

    Returns:
        Normalized base URL.

    Example:
        >>> normalize_base_url(None, "openai")
        'https://api.openai.com/v1'
        >>> normalize_base_url(None, "openai-responses")
        'https://api.openai.com/v1'
        >>> normalize_base_url(None, "openai-compatible")
        'http://localhost:1234/v1'

    """
    if not url:
        if provider in (OPENAI_RESPONSES, "openai"):
            return OPENAI_BASE_URL
        return DEFAULT_BASE_URL
    return url.rstrip("/")


# ── ProviderRegistry ─────────────────────────────────────────────────────────

ProviderFactory = Callable[["LanguageModel"], "LLMClient"]


@dataclass
class ProviderInfo:
    """Metadata for a registered provider.

    Attributes:
        id: Unique provider identifier.
        factory: Factory callable that creates an ``LLMClient`` from a
            ``LanguageModel`` configuration.
        description: Human-readable description of the provider.
        supported_models: Optional list of supported model identifiers.
    """

    id: str
    factory: ProviderFactory
    description: str = ""
    supported_models: list[str] | None = None


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
            # Normalize metadata.id too, if set
            metadata = replace(metadata, id=resolve_provider(metadata.id))
        if metadata is None:
            metadata = ProviderInfo(id=provider_id, factory=factory, description="")
        if metadata.id != provider_id:
            raise ValueError(
                f"metadata.id ({metadata.id!r}) conflicts with provider_id ({provider_id!r})"
            )

        self._providers[provider_id] = replace(metadata, id=provider_id, factory=factory)

    def create_client(self, model_config: LanguageModel) -> LLMClient:
        """Create an ``LLMClient`` for the given model configuration.

        Args:
            model_config: Language model configuration with ``provider``
                field identifying the desired provider.

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
        return info.factory(model_config)

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
    default providers (``openai-responses`` → ``OpenAICompatibleClient``).

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
    def _openai_responses_factory(model_config: LanguageModel) -> Any:
        # Deferred local import to prevent circular imports:
        # core.providers → agent.llm_client → core.providers
        from tinycua_sdk.agent.llm_client import OpenAIResponsesClient  # noqa: PLC0415

        return OpenAIResponsesClient(model_config)


    registry.register(
        OPENAI_RESPONSES,
        _openai_responses_factory,
        ProviderInfo(
            id=OPENAI_RESPONSES,
            factory=_openai_responses_factory,
            description="OpenAI Responses API",
        ),
    )


__all__ = [
    "DEFAULT_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_COMPATIBLE",
    "OPENAI_RESPONSES",
    "ProviderFactory",
    "ProviderInfo",
    "ProviderRegistry",
    "get_provider_registry",
    "normalize_base_url",
    "resolve_provider",
]
