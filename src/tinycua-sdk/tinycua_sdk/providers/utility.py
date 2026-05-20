"""Provider resolution, URL normalization, and factory types.

Extracted from ``core/providers.py`` — all provider resolution logic
lives here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinycua_sdk.agent.llm_client import LLMClient
    from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua_sdk.providers.constants import (
    DEFAULT_BASE_URL,
    OPENAI_BASE_URL,
    OPENAI_CHAT_COMPLETIONS,
    OPENAI_RESPONSES,
    _PROVIDER_ALIASES,
)

logger = logging.getLogger(__name__)


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
        'openai-responses'
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
        if provider in (OPENAI_RESPONSES, OPENAI_CHAT_COMPLETIONS, "openai"):
            return OPENAI_BASE_URL
        return DEFAULT_BASE_URL
    return url.rstrip("/")


# ── Factory types ─────────────────────────────────────────────────────────────

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


__all__ = [
    "ProviderFactory",
    "ProviderInfo",
    "normalize_base_url",
    "resolve_provider",
]
