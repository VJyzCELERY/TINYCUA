"""LLM provider resolution and normalization.

This module provides centralized provider resolution and URL normalization
for the TINYCUA SDK. It unifies all OpenAI-compatible endpoints under a single
canonical identifier while maintaining backward-compatible aliases.
"""

import logging
from typing import Final

logger = logging.getLogger(__name__)

#: The canonical identifier for OpenAI-compatible endpoints.
OPENAI_COMPATIBLE: Final = "openai-compatible"

#: Default base URL for local OpenAI-compatible endpoints.
DEFAULT_BASE_URL: Final = "http://localhost:1234/v1"

#: Backward-compatible aliases that map to the canonical identifier.
_PROVIDER_ALIASES: Final[dict[str, str]] = {
    "lmstudio": OPENAI_COMPATIBLE,
    "ollama": OPENAI_COMPATIBLE,
    # "openai" maps to itself
    "openai": "openai",
}

#: Valid provider identifiers (canonical + aliases + future stubs).
VALID_PROVIDERS: Final[frozenset[str]] = frozenset(
    {OPENAI_COMPATIBLE, "openai", "anthropic"} | set(_PROVIDER_ALIASES.keys())
)


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
        >>> resolve_provider("LMSTUDIO")
        'openai-compatible'

    """
    normalized = provider.lower().strip()
    canonical = _PROVIDER_ALIASES.get(normalized, normalized)
    if normalized != canonical and normalized in _PROVIDER_ALIASES:
        logger.info(
            "Provider alias '%s' resolved to canonical '%s'",
            normalized,
            canonical,
        )
    return canonical


def normalize_base_url(url: str | None) -> str:
    """Normalize a base URL.

    - If None/empty, returns DEFAULT_BASE_URL.
    - Strips trailing slash to prevent double slashes.
    - Does NOT append /v1 (user must provide full URL).

    Args:
        url: Raw base URL.

    Returns:
        Normalized base URL.

    Example:
        >>> normalize_base_url(None)
        'http://localhost:1234/v1'
        >>> normalize_base_url("http://localhost:1234/v1")
        'http://localhost:1234/v1'
        >>> normalize_base_url("http://localhost:1234/v1/")
        'http://localhost:1234/v1'

    """
    if not url:
        return DEFAULT_BASE_URL
    return url.rstrip("/")


__all__ = [
    "OPENAI_COMPATIBLE",
    "DEFAULT_BASE_URL",
    "VALID_PROVIDERS",
    "resolve_provider",
    "normalize_base_url",
]
