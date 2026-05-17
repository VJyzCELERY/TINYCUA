"""Conftest for integration tests."""

import os

import httpx
import pytest


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


def _build_auth_headers() -> dict[str, str]:
    """Build auth headers matching OpenAICompatibleClient logic."""
    api_key = os.environ.get("LLM_API_KEY", "")
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _probe_server(base_url: str, model: str, headers: dict) -> bool:
    """Check whether the LLM server is reachable and responds to basic requests."""
    try:
        httpx.get(f"{base_url}/models", headers=headers, timeout=5).raise_for_status()
        resp = httpx.post(
            f"{base_url}/responses",
            headers=headers,
            json={
                "model": model,
                "input": [{"role": "user", "content": "hi"}],
                "max_output_tokens": 1,
                "stream": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception:
        return False


def _probe_tool_choice(base_url: str, model: str, headers: dict) -> bool:
    """Check whether the provider supports forced ``tool_choice``.

    Sends a minimal /responses request with a forced function tool_choice and
    a dummy tool definition. Returns True only when the provider accepts the
    payload (HTTP 2xx).
    """
    try:
        resp = httpx.post(
            f"{base_url}/responses",
            headers=headers,
            json={
                "model": model,
                "input": [{"role": "user", "content": "what is the weather?"}],
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
                "max_output_tokens": 1,
                "stream": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when LLM server is unreachable or incompatible."""
    base_url = os.environ.get(
        "TINYCUA_BASE_URL",
        os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
    )
    model = os.environ.get("TINYCUA_MODEL", "qwen/qwen3.5-9b")
    headers = _build_auth_headers()

    reachable = _probe_server(base_url, model, headers)
    tool_choice_supported = reachable and _probe_tool_choice(base_url, model, headers)

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
