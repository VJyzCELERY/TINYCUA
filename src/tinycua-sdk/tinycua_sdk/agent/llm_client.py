"""LLM client ABC and OpenAI-compatible implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from tinycua_sdk.agent.llm_model import LanguageModel


class LLMClient(ABC):
    """Abstract base for LLM API clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> dict[str, Any]:
        """Send chat request and return normalized response."""


class OpenAICompatibleClient(LLMClient):
    """Client for OpenAI-compatible endpoints using httpx."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self, model_config: LanguageModel) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {}
            api_key = model_config.api_key.get_secret_value()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            base_url = model_config.base_url or "https://api.openai.com/v1"
            self._client = httpx.AsyncClient(
                base_url=base_url, headers=headers, timeout=60.0
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> dict[str, Any]:
        """Send a chat completion request and return the normalized response."""
        client = self._get_client(model_config)

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "messages": messages,
        }

        for field in (
            "temperature", "max_tokens", "top_p", "frequency_penalty",
            "presence_penalty", "stop", "seed", "response_format",
            "tool_choice", "logprobs", "top_logprobs", "user",
        ):
            value = getattr(model_config, field)
            if value is not None:
                payload[field] = value

        if tools:
            payload["tools"] = tools
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                {
                    "id": tc["id"],
                    "type": tc["type"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in message["tool_calls"]
            ]

        return {
            "content": message.get("content"),
            "tool_calls": tool_calls,
            "usage": data.get("usage"),
        }
