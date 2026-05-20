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
    """Centralized LLM configuration resolved from environment variables.

    Resolution order: TINYCUA_* vars first, then LLM_* fallbacks.
    """

    provider: str = "openai-responses"
    model: str = ""
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "dummy"


def resolve_integration_llm_config() -> IntegrationLLMConfig:
    """Resolve integration test LLM config from environment variables.

    Uses TINYCUA_* vars first, falls back to LLM_* vars for compatibility,
    then to sensible defaults.
    """
    return IntegrationLLMConfig(
        provider=os.environ.get(
            "TINYCUA_PROVIDER", os.environ.get("LLM_PROVIDER", "openai-responses")
        ),
        model=os.environ.get(
            "TINYCUA_MODEL",
            os.environ.get("LLM_MODEL", ""),
        ),
        base_url=os.environ.get(
            "TINYCUA_BASE_URL",
            os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        ),
        api_key=os.environ.get(
            "TINYCUA_API_KEY",
            os.environ.get("LLM_API_KEY", "dummy"),
        ),
    )


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )
    config.addinivalue_line(
        "markers",
        "integration_tool_choice: marks tests requiring forced tool_choice support "
        "(auto-skipped when provider rejects the payload)",
    )


def _build_auth_headers(api_key: str | None = None) -> dict[str, str]:
    """Build auth headers matching OpenAICompatibleClient logic."""
    key = api_key or os.environ.get("LLM_API_KEY", "")
    headers: dict[str, str] = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


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

    Uses the provider-appropriate endpoint instead of hardcoding /responses.
    """
    try:
        httpx.get(f"{base_url}/models", headers=headers, timeout=5).raise_for_status()
        endpoint = _probe_endpoint(provider)
        payload: dict = {
            "model": model,
            "max_output_tokens": 1,
            "stream": False,
        }
        if provider == "openai-chat-completions":
            payload["messages"] = [{"role": "user", "content": "hi"}]
        else:
            payload["input"] = [{"role": "user", "content": "hi"}]

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
    Returns True only when the provider accepts the payload (HTTP 2xx).
    """
    try:
        endpoint = _probe_endpoint(provider)
        payload: dict = {
            "model": model,
            "max_output_tokens": 1,
            "stream": False,
            "tools": [
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
            ],
            "tool_choice": {"type": "function", "name": "get_weather"},
        }
        if provider == "openai-chat-completions":
            payload["messages"] = [{"role": "user", "content": "what is the weather?"}]
        else:
            payload["input"] = [{"role": "user", "content": "what is the weather?"}]

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


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when LLM server is unreachable or incompatible.

    Only probes when live LLM tests (``integration`` marker) are collected.
    Tool-choice probe is further gated to tests with the
    ``integration_tool_choice`` marker.
    """
    live_items = [item for item in items if "integration" in item.keywords]
    tool_choice_items = [
        item for item in items if "integration_tool_choice" in item.keywords
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
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_mark)
    elif not tool_choice_supported:
        skip_tc_mark = pytest.mark.skip(
            reason="LLM server does not support forced tool_choice — skipping "
            "tool-choice integration tests"
        )
        for item in items:
            if "integration_tool_choice" in item.keywords:
                item.add_marker(skip_tc_mark)
