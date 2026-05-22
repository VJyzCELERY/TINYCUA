"""Conftest for integration tests.

Provides a centralized LLM config resolver and gateable provider probes.
Probes only run when live LLM tests are actually collected (ISSUE-004).
Model/provider resolution is consistent across conftest and tests (ISSUE-005).
Readiness probes are provider-aware, using /responses or /chat/completions (ISSUE-006).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import pytest


@dataclass(frozen=True)
class IntegrationLLMConfig:
    """Centralized LLM configuration resolved from environment variables."""

    provider: str = "openai-chat-completions"
    model: str = ""
    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""


def resolve_integration_llm_config() -> IntegrationLLMConfig:
    """Resolve integration test LLM config from environment variables.

    Resolution mirrors the runtime provider clients:
    - Provider-specific env vars take precedence over LLM_* fallbacks.
    - Base URL: provider-specific > LLM_BASE_URL > localhost default.
    - API key: provider-specific only (no generic API key fallback).
    - Model: provider-specific > LLM_MODEL > empty string default.
    """
    provider = os.environ.get("LLM_PROVIDER", "")
    if not provider:
        # Auto-detect from provider-specific env vars
        if os.environ.get("OPENAI_RESPONSES_MODEL") or os.environ.get(
            "OPENAI_RESPONSES_API_KEY"
        ):
            provider = "openai-responses"
        elif os.environ.get("OPENAI_CHAT_COMPLETIONS_MODEL") or os.environ.get(
            "OPENAI_CHAT_COMPLETIONS_API_KEY"
        ):
            provider = "openai-chat-completions"
        else:
            provider = "openai-chat-completions"

    if provider == "openai-responses":
        model = os.environ.get(
            "OPENAI_RESPONSES_MODEL", os.environ.get("LLM_MODEL", "")
        )
        base_url = os.environ.get(
            "OPENAI_RESPONSES_BASE_URL",
            os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        )
        api_key = os.environ.get("OPENAI_RESPONSES_API_KEY", "")
    else:
        model = os.environ.get(
            "OPENAI_CHAT_COMPLETIONS_MODEL", os.environ.get("LLM_MODEL", "")
        )
        base_url = os.environ.get(
            "OPENAI_CHAT_COMPLETIONS_BASE_URL",
            os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        )
        api_key = os.environ.get("OPENAI_CHAT_COMPLETIONS_API_KEY", "")

    return IntegrationLLMConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )
    config.addinivalue_line(
        "markers",
        "integration_tool_choice: marks tests requiring forced tool_choice support "
        "(auto-skipped when provider rejects the payload or model does not call a tool)",
    )


def _build_auth_headers(api_key: str | None = None) -> dict[str, str]:
    """Build auth headers matching provider client logic."""
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _forced_tool_choice(provider: str, name: str) -> str | dict:
    """Return a provider-compatible forced tool_choice value.

    - openai-chat-completions → ``{"type": "function", "function": {"name": name}}``
      (the correct OpenAI Chat Completions API format for forcing a specific tool)
    - openai-responses / other → ``"required"`` (the only form LM Studio / local
      providers accept for the Responses endpoint; Chat Completions object form
      is typically rejected)

    The ``_probe_tool_choice`` function sends this value to the live server and
    also verifies the response body contains actual ``tool_calls``, so the
    ``integration_tool_choice`` marker gates tests correctly: if the server
    rejects the payload OR accepts it but the model does not call a tool, the
    probe fails and tests are skipped.
    """
    if provider == "openai-chat-completions":
        return {"type": "function", "function": {"name": name}}
    return "required"


def _probe_payload(provider: str, model: str, include_tools: bool = False) -> dict:
    """Build a provider-native probe payload.

    Returns a minimal payload dict with provider-correct field names
    (e.g. ``max_tokens`` for chat completions, ``max_output_tokens`` for
    responses) and message/tools shapes.  When *include_tools* is true the
    payload includes a single tool and the appropriate tool_choice value.
    """
    endpoint = _probe_endpoint(provider)
    is_chat = endpoint == "/chat/completions"

    payload: dict[str, object] = {
        "model": model,
        "max_output_tokens": 1,
        "stream": False,
    }
    if is_chat:
        payload["max_tokens"] = payload.pop("max_output_tokens")
        payload["messages"] = [{"role": "user", "content": "hi"}]
    else:
        payload["input"] = [{"role": "user", "content": "hi"}]

    if include_tools:
        if is_chat:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string", "description": "City name"}
                            },
                            "required": ["city"],
                        },
                    },
                }
            ]
        else:
            payload["tools"] = [
                {
                    "type": "function",
                    "name": "get_weather",
                    "description": "Get weather for a city.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name"}
                        },
                        "required": ["city"],
                    },
                }
            ]
        payload["tool_choice"] = _forced_tool_choice(provider, "get_weather")
        if is_chat:
            payload["messages"] = [{"role": "user", "content": "what is the weather?"}]
        else:
            payload["input"] = [{"role": "user", "content": "what is the weather?"}]

    return payload


def _probe_endpoint(provider: str) -> str:
    """Return the probe endpoint path for the given provider.

    - openai-responses → /responses
    - openai-chat-completions → /chat/completions
    """
    if provider == "openai-chat-completions":
        return "/chat/completions"
    return "/responses"


def _probe_server(base_url: str, model: str, headers: dict, provider: str) -> bool:
    """Check whether the LLM server is reachable and responds to basic requests.

    Uses the provider-appropriate endpoint and payload shape instead of
    hardcoding /responses with Responses-only fields.
    """
    try:
        httpx.get(f"{base_url}/models", headers=headers, timeout=5).raise_for_status()
        endpoint = _probe_endpoint(provider)
        payload = _probe_payload(provider, model, include_tools=False)

        resp = httpx.post(
            f"{base_url}{endpoint}",
            headers=headers,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception:
        return False


def _probe_tool_choice(base_url: str, model: str, headers: dict, provider: str) -> bool:
    """Check whether the provider supports forced ``tool_choice``.

    Uses the provider-appropriate endpoint and payload shape.
    Returns True only when the provider accepts the payload (HTTP 2xx)
    **and** the response body contains actual ``tool_calls`` entries
    (i.e. the model honoured the forced tool_choice).

    This two-level check prevents false positives where the API accepts
    a ``tool_choice`` value syntactically but the underlying model does
    not actually call a tool (observed with LM Studio / local Qwen when
    ``tool_choice="required"`` is accepted at the HTTP level but the
    model returns a plain response).
    """
    try:
        endpoint = _probe_endpoint(provider)
        payload = _probe_payload(provider, model, include_tools=True)

        resp = httpx.post(
            f"{base_url}{endpoint}",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

        # Level 2: verify the model actually called a tool.
        # A syntactically valid 200 response with no tool_calls means the
        # provider/model does not truly honour forced tool_choice.
        body = resp.json()
        if provider == "openai-chat-completions":
            choices = body.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                if msg.get("tool_calls"):
                    return True
            return False

        # openai-responses endpoint response structure
        output = body.get("output", [])
        for item in output:
            if item.get("type") == "function_call" or item.get("tool_calls"):
                return True
        return False

    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when LLM server is unreachable or incompatible.

    Only probes when live LLM tests (``integration`` marker) are collected.
    Tool-choice probe is further gated to tests with the
    ``integration_tool_choice`` marker.
    """
    live_items = [
        item for item in items
        if item.get_closest_marker("integration") is not None
    ]
    tool_choice_items = [
        item for item in items
        if item.get_closest_marker("integration_tool_choice") is not None
    ]

    # Skip provider probes entirely when no live LLM tests are collected
    if not live_items:
        return

    cfg = resolve_integration_llm_config()
    headers = _build_auth_headers(cfg.api_key)

    reachable = _probe_server(cfg.base_url, cfg.model, headers, cfg.provider)
    tool_choice_supported = (
        reachable
        and tool_choice_items
        and _probe_tool_choice(cfg.base_url, cfg.model, headers, cfg.provider)
    )

    if not reachable:
        skip_mark = pytest.mark.skip(reason="LLM server not reachable/unusable")
        for item in live_items:
            item.add_marker(skip_mark)
    elif not tool_choice_supported:
        skip_tc_mark = pytest.mark.skip(
            reason="LLM server does not support forced tool_choice — skipping "
            "tool-choice integration tests"
        )
        for item in tool_choice_items:
            item.add_marker(skip_tc_mark)
