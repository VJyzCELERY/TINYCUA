"""Conftest for integration tests.

Provides LLM config resolution and server probing for native tool
end-to-end tests. Follows the tinycua-sdk integration test pattern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import dotenv
import httpx
import pytest


# Load .env.test or .env.test.example automatically
_env_loaded = False


def _ensure_env_loaded() -> None:
    """Load environment from .env.test (or .env.test.example as fallback)."""
    global _env_loaded
    if _env_loaded:
        return

    probe_dir = Path(__file__).resolve().parent.parent.parent  # tests/ -> project root
    for candidate in (probe_dir / ".env.test", probe_dir / ".env.test.example"):
        if candidate.exists():
            dotenv.load_dotenv(candidate, override=False)
            break

    _env_loaded = True


@dataclass(frozen=True)
class IntegrationLLMConfig:
    """LLM configuration resolved from environment variables."""

    provider: str = "openai-chat-completions"
    model: str = ""
    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""


def resolve_integration_llm_config() -> IntegrationLLMConfig:
    """Resolve integration test LLM config from environment variables.

    Resolution order:
      - Provider-specific env vars (OPENAI_CHAT_COMPLETIONS_*) take priority.
      - LLM_* fallbacks are used when no provider-specific var is set.
    """
    _ensure_env_loaded()

    model = os.environ.get(
        "OPENAI_CHAT_COMPLETIONS_MODEL", os.environ.get("LLM_MODEL", "")
    )
    base_url = os.environ.get(
        "OPENAI_CHAT_COMPLETIONS_BASE_URL",
        os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
    )
    api_key = os.environ.get("OPENAI_CHAT_COMPLETIONS_API_KEY", "")

    return IntegrationLLMConfig(
        provider="openai-chat-completions",
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring a live LLM server"
    )


def _probe_server(base_url: str, model: str, api_key: str) -> bool:
    """Check whether the LLM server is reachable."""
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client() as client:
            # First check /models endpoint
            client.get(
                f"{base_url}/models", headers=headers, timeout=5
            ).raise_for_status()

            # Then try a minimal completion
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "stream": False,
            }
            resp = client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when the LLM server is unreachable."""
    live_items = [
        item for item in items if item.get_closest_marker("integration") is not None
    ]

    if not live_items:
        return

    cfg = resolve_integration_llm_config()
    reachable = _probe_server(cfg.base_url, cfg.model, cfg.api_key)

    if not reachable:
        skip_mark = pytest.mark.skip(
            reason="LLM server not reachable — skipping integration tests"
        )
        for item in live_items:
            item.add_marker(skip_mark)
