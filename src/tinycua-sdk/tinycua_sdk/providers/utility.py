"""Provider resolution, URL normalization, and factory types.

Extracted from ``core/providers.py`` — all provider resolution logic
lives here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from tinycua_sdk.agent.llm_client import LLMClient
    from tinycua_sdk.agent.llm_model import LanguageModel
    from tinycua_sdk.models.attachment import FileAttachment

from tinycua_sdk.providers.constants import _PROVIDER_ALIASES

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


def normalize_base_url(url: str) -> str:
    """Normalize a base URL for consistent cache scoping.

    Raises:
        ValueError: If ``url`` is empty.

    Strips trailing slashes and lowercases scheme/host so that
    equivalent endpoint spellings (e.g. ``HTTPS://API.OPENAI.COM/v1/``
    and ``https://api.openai.com/v1``) produce the same hash.

    Pure URL normalizer — does NOT resolve environment variables or provider
    defaults. Each provider client is responsible for its own resolution.

    Args:
        url: Raw base URL (must not be None/empty).

    Returns:
        Normalized base URL with trailing slash removed and scheme/host
        lowercased.

    Example:
        >>> normalize_base_url("http://localhost:1234/v1/")
        'http://localhost:1234/v1'
        >>> normalize_base_url("https://api.openai.com/v1")
        'https://api.openai.com/v1'
        >>> normalize_base_url("HTTPS://API.OPENAI.COM/v1/")
        'https://api.openai.com/v1'

    """
    from urllib.parse import urlparse, urlunparse

    if not url:
        raise ValueError("base_url must not be empty")

    url = url.rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme:
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
    return url


# ── MIME type helpers ─────────────────────────────────────────────────────────

_TEXT_MIME_TYPES: set[str] = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "text/xml",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-yaml",
    "text/x-python",
    "text/x-script.python",
}


def is_text_mime(mime_type: str) -> bool:
    """Return True if the MIME type represents a text format.

    Text files can be sent inline as ``{"type": "text", "text": "..."}``
    instead of requiring upload via ``/v1/files``. This works with any
    OpenAI-compatible provider (local servers, LM Studio, Ollama, etc.).

    Strips charset parameters (e.g. ``"application/json; charset=utf-8"``)
    before matching so that parameterized MIME types are correctly
    classified as text.
    """
    base = mime_type.split(";")[0].strip()
    if base.startswith("text/"):
        return True
    return base in _TEXT_MIME_TYPES


# ── Attachment materialization helpers ─────────────────────────────────────────


def materialize_streaming_image(attachment: FileAttachment) -> str:
    """Read all base64 chunks from a streaming image attachment.

    Collects all base64-encoded chunks from the attachment and returns a
    ``data:{mime_type};base64,{content}`` data URL string.  This avoids
    duplicate chunk-reader logic in every provider translation function.

    Args:
        attachment: A ``StreamingFileAttachment`` with an image MIME type.
            Must have been created with ``stream=True``.

    Returns:
        A data URL string suitable for inline image content parts.

    Raises:
        AttributeError: If ``attachment`` does not provide
            ``iter_base64_chunks`` (not a streaming attachment).
    """
    data_chunks: list[str] = list(attachment.iter_base64_chunks())
    data = "".join(data_chunks)
    return f"data:{attachment.mime_type};base64,{data}"


def materialize_streaming_text(attachment: FileAttachment) -> str:
    """Read all raw chunks from a streaming text attachment.

    Collects all raw bytes from the attachment and decodes them as UTF-8.
    This avoids duplicate chunk-reader logic in every provider translation
    function.

    Args:
        attachment: A ``StreamingFileAttachment`` with a text MIME type.
            Must have been created with ``stream=True``.

    Returns:
        Decoded text content as a string.

    Raises:
        AttributeError: If ``attachment`` does not provide
            ``iter_raw_chunks`` (not a streaming attachment).
    """
    return b"".join(attachment.iter_raw_chunks()).decode(
        "utf-8",
        errors="replace",
    )


# ── Factory types ─────────────────────────────────────────────────────────────

class ProviderFactory(Protocol):
    """Protocol for provider factory callables.

    Factory functions must accept a ``LanguageModel`` configuration
    and an optional keyword-only ``upload_session`` argument.
    """

    def __call__(
        self,
        model_config: "LanguageModel",
        *,
        upload_session: Any | None = None,
    ) -> "LLMClient":
        """Create an LLM client for the given model configuration.

        Args:
            model_config: The language model configuration to use.
            upload_session: Optional upload session for file caching.

        Returns:
            An ``LLMClient`` instance configured for the provider.
        """
        ...


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
    "is_text_mime",
    "materialize_streaming_image",
    "materialize_streaming_text",
    "normalize_base_url",
    "resolve_provider",
]
