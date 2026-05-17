"""Core SDK abstractions."""

from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError, ProviderNotSupportedError
from tinycua_sdk.core.providers import (
    DEFAULT_BASE_URL,
    OPENAI_BASE_URL,
    OPENAI_COMPATIBLE,
    OPENAI_RESPONSES,
    ProviderFactory,
    ProviderInfo,
    ProviderRegistry,
    get_provider_registry,
    normalize_base_url,
    resolve_provider,
)

__all__ = [
    # Exceptions
    "ProviderApiError",
    "ProviderAuthError",
    "ProviderNotSupportedError",
    # Providers
    "OPENAI_COMPATIBLE",
    "OPENAI_RESPONSES",
    "DEFAULT_BASE_URL",
    "OPENAI_BASE_URL",
    "resolve_provider",
    "normalize_base_url",
    "ProviderFactory",
    "ProviderInfo",
    "ProviderRegistry",
    "get_provider_registry",
]
