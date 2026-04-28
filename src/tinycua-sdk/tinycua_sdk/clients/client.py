"""Responses client for making API calls."""

import os
import uuid
from typing import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from tinycua_sdk.core.providers import DEFAULT_BASE_URL
from tinycua_sdk.models.request import ResponseRequest
from tinycua_sdk.models.response import Response, StreamEvent, StreamEventType, Usage


class ResponsesClient:
    """Client for the OpenAI Responses API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
    ):
        """Initialize the ResponsesClient.

        Args:
            base_url: Base URL for the API. Defaults to TINYCUA_API_URL env var.
            api_key: API key for authentication. Defaults to TINYCUA_API_KEY env var.
            max_retries: Maximum number of retry attempts for failed requests.

        """
        self.base_url = base_url or os.getenv(
            "TINYCUA_API_URL", DEFAULT_BASE_URL
        )
        self.api_key = api_key or os.getenv("TINYCUA_API_KEY", "")
        self.max_retries = max_retries

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60.0,
            headers=headers,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create(self, request: ResponseRequest) -> Response:
        """Create a non-streaming response."""
        trace_id = str(uuid.uuid4())

        # Build messages from input
        messages = []
        system_prompt = None
        for msg in request.input:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                messages.append(msg)

        # Use chat completions format for OpenAI-compatible endpoints
        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if system_prompt:
            payload["messages"].insert(0, {"role": "system", "content": system_prompt})

        if request.tools:
            payload["tools"] = [
                t.to_config() if hasattr(t, "to_config") else t for t in request.tools
            ]

        # Try responses API first, fall back to chat completions
        try:
            response = await self._client.post(
                "/responses",
                json=payload,
                headers={"X-Trace-Id": trace_id},
            )
            response.raise_for_status()
            data = response.json()

            # Extract from responses format
            choices = data.get("choices", [])
            if not choices:
                # Try chat completions format
                response = await self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers={"X-Trace-Id": trace_id},
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
        except httpx.HTTPStatusError:
            # Fall back to chat completions
            response = await self._client.post(
                "/chat/completions",
                json=payload,
                headers={"X-Trace-Id": trace_id},
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])

        # Extract usage - chat completions format differs
        usage_data = data.get("usage", {})
        if isinstance(usage_data, dict):
            usage = {
                "input_tokens": usage_data.get("prompt_tokens", 0),
                "output_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }
        else:
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        return Response(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=choices,
            usage=Usage(**usage),
        )

    async def stream(self, request: ResponseRequest) -> AsyncIterator[StreamEvent]:
        """Create a streaming response."""
        trace_id = str(uuid.uuid4())

        # Build messages from input
        messages = []
        system_prompt = None
        for msg in request.input:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                messages.append(msg)

        # Use chat completions format for OpenAI-compatible endpoints
        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        if system_prompt:
            payload["messages"].insert(0, {"role": "system", "content": system_prompt})

        if request.tools:
            payload["tools"] = [
                t.to_config() if hasattr(t, "to_config") else t for t in request.tools
            ]

        # Use chat completions for streaming (more compatible)
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=payload,
            headers={"X-Trace-Id": trace_id},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        import json

                        event_data = json.loads(data)
                        yield StreamEvent(type=StreamEventType.CONTENT, data=event_data)
                    except json.JSONDecodeError:
                        pass


__all__ = ["ResponsesClient"]
