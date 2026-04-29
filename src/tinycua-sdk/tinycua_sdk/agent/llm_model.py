"""LLM Model configuration value object."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from tinycua_sdk.core.providers import resolve_provider


class LLMModel(BaseModel):
    """Immutable LLM endpoint configuration.

    Pure value object — no I/O, no persistence methods.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    max_context: int = 128_000
    temperature: float = 1.0
    system_prompt: str = "You are a helpful assistant."

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        """Normalize provider identifier."""
        return resolve_provider(v)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMModel":
        """Deserialize from plain dict."""
        return cls(**data)
