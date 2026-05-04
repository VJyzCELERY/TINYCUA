"""Language model configuration value object."""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from tinycua_sdk.core.providers import resolve_provider


class LanguageModel(BaseModel):
    """Immutable language model endpoint configuration.

    Pure value object — no I/O, no persistence methods.
    Supports all OpenAI-compatible API parameters.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    temperature: float = 1.0
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: str | list[str] | None = None
    seed: int | None = None
    response_format: dict | None = None
    tool_choice: str | dict | None = None
    logprobs: bool = False
    top_logprobs: int | None = None
    user: str | None = None
    system_prompt: str = "You are a helpful assistant."
    strip_thinking: bool = False
    max_context: int = 128_000

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        """Normalize provider identifier."""
        return resolve_provider(v)

    @field_validator("api_key", mode="before")
    @classmethod
    def _resolve_env_vars(cls, v: str | SecretStr) -> str:
        """Resolve ${VAR_NAME} patterns in api_key from environment variables."""
        if isinstance(v, SecretStr):
            v = v.get_secret_value()
        value = v

        def _replacer(match: re.Match) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            return match.group(0)

        resolved = re.sub(r"\$\{(\w+)\}", _replacer, value)
        return resolved

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict, excluding None values."""
        return self.model_dump(exclude_none=True)

    def to_json(self) -> str:
        """Serialize to indented JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LanguageModel":
        """Deserialize from plain dict."""
        return cls(**data)

    @classmethod
    def from_json(cls, data: str) -> "LanguageModel":
        """Deserialize from JSON string."""
        import json

        return cls(**json.loads(data))


LLMModel = LanguageModel
