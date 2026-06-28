"""Local model endpoint configuration for TinyCUA nodes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LocalModelConfig:
    """Configuration for local model endpoint.

    Used by nodes to configure LLM client for their calls.

    Attributes:
        base_url: Base URL for the local model endpoint.
        model: Model name or identifier.
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate (None = unlimited).
    """

    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 30.0
    temperature: float = 0.7
    max_tokens: int | None = None
