"""Conftest for integration tests."""

import os

import httpx
import pytest


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )


def _build_auth_headers() -> dict[str, str]:
    """Build auth headers matching OpenAICompatibleClient logic."""
    api_key = os.environ.get("TINYCUA_API_KEY", "")
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when LLM server is unreachable."""
    base_url = os.environ.get(
        "TINYCUA_BASE_URL",
        os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
    )
    model = os.environ.get("TINYCUA_MODEL", "qwen/qwen3.5-9b")
    headers = _build_auth_headers()
    try:
        httpx.get(f"{base_url}/models", headers=headers, timeout=5).raise_for_status()
        resp = httpx.post(
            f"{base_url}/responses",
            headers=headers,
            json={
                "model": model,
                "input": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "stream": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
        reachable = True
    except Exception:
        reachable = False

    if not reachable:
        skip_mark = pytest.mark.skip(reason="LLM server not reachable/unusable")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_mark)
