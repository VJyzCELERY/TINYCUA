"""Language model configuration value object."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator

from tinycua_sdk.providers.utility import resolve_provider


# Mapping from normalized provider to its model-name environment variable.
_PROVIDER_MODEL_ENV: dict[str, str] = {
    "openai-responses": "OPENAI_RESPONSES_MODEL",
    "openai-chat-completions": "OPENAI_CHAT_COMPLETIONS_MODEL",
}
_HARDCODED_DEFAULT_MODEL = "gpt-4o-mini"


class LanguageModel(BaseModel):
    """Immutable language model endpoint configuration.

    Pure value object — no I/O, no persistence methods.
    Supports all OpenAI-compatible API parameters.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = "openai-responses"
    model_name: str = ""
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
        """Normalize provider identifier via alias resolution only."""
        return resolve_provider(v)

    @field_validator("api_key", mode="before")
    @classmethod
    def _resolve_env_vars(cls, v: str | SecretStr) -> SecretStr:
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
        return SecretStr(resolved)

    @model_validator(mode="after")
    def _resolve_model_env(self) -> "LanguageModel":
        """Resolve empty model_name from provider-specific env vars.

        Priority: provider-specific model env var > LLM_MODEL > hardcoded default.
        If model_name was explicitly set (non-empty), it is kept unchanged.
        """
        if self.model_name:
            return self
        model_env = _PROVIDER_MODEL_ENV.get(self.provider)
        resolved: str = ""
        if model_env:
            resolved = os.environ.get(model_env, "")
        if not resolved:
            resolved = os.environ.get("LLM_MODEL", "")
        if not resolved:
            resolved = _HARDCODED_DEFAULT_MODEL
        object.__setattr__(self, "model_name", resolved)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict, excluding None values."""
        return self.model_dump(exclude_none=True)

    def to_json(self) -> str:
        """Serialize to indented JSON string.

        Warning: The api_key is serialized as its plain value (not redacted).
        Do not write the output of this method to logs or shared files,
        as it will expose the API key in plaintext.
        """
        data = self.model_dump(exclude_none=True)
        if isinstance(data.get("api_key"), SecretStr):
            data["api_key"] = data["api_key"].get_secret_value()
        return json.dumps(data, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LanguageModel":
        """Deserialize from plain dict.

        Args:
            data: A dictionary of model configuration values.

        Returns:
            A new LanguageModel instance.
        """
        return cls(**data)

    @classmethod
    def from_json(cls, data: str) -> "LanguageModel":
        """Deserialize from JSON string.

        Note: api_key must be provided as a plain string in JSON.

        Args:
            data: A JSON string of model configuration values.

        Returns:
            A new LanguageModel instance.
        """
        parsed = json.loads(data)
        if isinstance(parsed.get("api_key"), str):
            parsed["api_key"] = SecretStr(parsed["api_key"])
        return cls(**parsed)


__all__ = ["LanguageModel"]
