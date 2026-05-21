"""Provider package — client implementations, registry, and utilities.

Re-exports all public symbols from sub-modules for ergonomic imports.
"""

from tinycua_sdk.providers.constants import (
    DEFAULT_BASE_URL,
    OPENAI_BASE_URL,
    OPENAI_CHAT_COMPLETIONS,
    OPENAI_COMPATIBLE,
    OPENAI_RESPONSES,
)
from tinycua_sdk.providers.open_ai_chat_completions import (
    OpenAIChatCompletionsClient,
)
from tinycua_sdk.providers.open_ai_responses import (
    OpenAIResponsesClient,
)
from tinycua_sdk.providers.registry import ProviderRegistry, get_provider_registry
from tinycua_sdk.providers.utility import (
    ProviderFactory,
    ProviderInfo,
    normalize_base_url,
    resolve_provider,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_CHAT_COMPLETIONS",
    "OPENAI_COMPATIBLE",
    "OPENAI_RESPONSES",
    "OpenAIChatCompletionsClient",
    "OpenAIResponsesClient",
    "ProviderFactory",
    "ProviderInfo",
    "ProviderRegistry",
    "get_provider_registry",
    "normalize_base_url",
    "resolve_provider",
]
