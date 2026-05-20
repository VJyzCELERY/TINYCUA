"""Provider constants — canonical identifiers, base URLs, and alias mappings.

All provider-related constants live here so that other sub-modules can
import them without circular dependencies.
"""

from __future__ import annotations

from typing import Final

#: The canonical identifier for OpenAI-compatible endpoints.
OPENAI_COMPATIBLE: Final = "openai-compatible"

#: The canonical identifier for OpenAI Responses API.
OPENAI_RESPONSES: Final = "openai-responses"

#: The canonical identifier for OpenAI Chat Completions API.
OPENAI_CHAT_COMPLETIONS: Final = "openai-chat-completions"

#: Default base URL for local OpenAI-compatible endpoints.
DEFAULT_BASE_URL: Final = "http://localhost:1234/v1"

#: Default base URL for OpenAI Responses API.
OPENAI_BASE_URL: Final = "https://api.openai.com/v1"

#: Backward-compatible aliases that map to the canonical identifier.
_PROVIDER_ALIASES: Final[dict[str, str]] = {
    "lmstudio": OPENAI_COMPATIBLE,
    "ollama": OPENAI_COMPATIBLE,
    "openai": OPENAI_RESPONSES,
}

__all__ = [
    "DEFAULT_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_CHAT_COMPLETIONS",
    "OPENAI_COMPATIBLE",
    "OPENAI_RESPONSES",
]
