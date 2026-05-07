"""LLM client ABC and OpenAI-compatible implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Send chat request and return normalized response.

        Args:
            messages: List of message dicts.
            tools: Optional list of tool schemas.
            model_config: Language model configuration.
            stream: When True, return an async iterator of SSE chunk events.

        Returns:
            Normalized response dict when stream=False, or an async iterator
            of event dicts when stream=True.
        """

    async def close(self) -> None:
        """Close and release any resources held by the client."""


class OpenAICompatibleClient(LLMClient):
    """Client for OpenAI-compatible endpoints using httpx."""

    def __init__(self) -> None:
        self._clients: dict[tuple[str, str], httpx.AsyncClient] = {}

    def _client_key(self, model_config: LanguageModel) -> tuple[str, str]:
        api_key = model_config.api_key.get_secret_value()
        base_url = model_config.base_url or "https://api.openai.com/v1"
        return (base_url, api_key)

    def _get_client(self, model_config: LanguageModel) -> httpx.AsyncClient:
        key = self._client_key(model_config)
        if key not in self._clients:
            api_key = key[1]
            headers: dict[str, str] = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            self._clients[key] = httpx.AsyncClient(
                base_url=key[0], headers=headers, timeout=60.0
            )
        return self._clients[key]

    async def close(self) -> None:
        """Close all cached HTTP clients and clear the cache."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Send a chat completion request.

        Args:
            messages: List of message dicts.
            tools: Optional list of tool schemas.
            model_config: Language model configuration.
            stream: When True, return an async generator of SSE chunk events.

        Returns:
            Normalized response dict when stream=False, or an async iterator
            of event dicts when stream=True.
        """
        if not stream:
            return await self._chat_sync(messages, tools, model_config)
        return self._chat_stream(messages, tools, model_config)

    async def _chat_sync(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> dict[str, Any]:
        """Non-streaming chat completion (original logic).

        Args:
            messages: List of message dicts.
            tools: Optional list of tool schemas.
            model_config: Language model configuration.

        Returns:
            Normalized response dict with content, tool_calls, and usage.
        """
        client = self._get_client(model_config)

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "messages": messages,
        }

        for field in (
            "temperature",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
            "response_format",
            "tool_choice",
            "logprobs",
            "top_logprobs",
            "user",
        ):
            value = getattr(model_config, field)
            if value is not None:
                payload[field] = value

        if tools:
            payload["tools"] = tools
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        try:
            response = await client.post("chat/completions", json=payload)
        except httpx.RequestError as e:
            raise RuntimeError(
                f"Failed to connect to LLM at {model_config.base_url}: {e}"
            ) from e
        response.raise_for_status()
        data = response.json()

        if "choices" not in data or not data["choices"]:
            raise RuntimeError(f"LLM response missing 'choices' field: {data}")
        choice = data["choices"][0]
        if "message" not in choice:
            raise RuntimeError(f"LLM response choice missing 'message' field: {choice}")
        message = choice["message"]

        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = []
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                tool_calls.append(
                    {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": func.get("name", ""),
                            "arguments": func.get("arguments", "{}"),
                        },
                    }
                )

        return {
            "content": message.get("content"),
            "tool_calls": tool_calls,
            "usage": data.get("usage"),
        }

    async def _chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming chat completion via SSE.

        Args:
            messages: List of message dicts.
            tools: Optional list of tool schemas.
            model_config: Language model configuration.

        Yields:
            Normalised event dicts for content deltas and tool call deltas.
        """
        client = self._get_client(model_config)

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "messages": messages,
        }

        for field in (
            "temperature",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
            "response_format",
            "tool_choice",
            "logprobs",
            "top_logprobs",
            "user",
        ):
            value = getattr(model_config, field)
            if value is not None:
                payload[field] = value

        if tools:
            payload["tools"] = tools
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        payload["stream"] = True

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    delta = data["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield {
                            "type": "response.output_text.delta",
                            "delta": delta["content"],
                            "item_id": data["choices"][0].get("id", ""),
                        }
                    elif delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            yield {
                                "type": "response.tool_call.delta",
                                "id": tc.get("id", ""),
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get(
                                    "arguments", ""
                                ),
                            }


__all__ = ["LLMClient", "OpenAICompatibleClient"]
