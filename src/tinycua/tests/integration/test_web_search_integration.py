"""Integration test for web_search against a real SearXNG endpoint.

Loads ``TINYCUA_SEARXNG_URL`` from ``.env.test`` / ``.env.test.example``
via the integration conftest. Skips when the env var is unset or the
SearXNG server is unreachable.
"""

from __future__ import annotations

import os

import httpx
import pytest


def _resolve_searxng_url() -> str:
    """Read TINYCUA_SEARXNG_URL from .env.test / .env.test.example."""
    from pathlib import Path

    import dotenv

    project_root = Path(__file__).resolve().parent.parent.parent
    for candidate in (project_root / ".env.test", project_root / ".env.test.example"):
        if candidate.exists():
            dotenv.load_dotenv(candidate, override=False)
            break
    return os.environ.get("TINYCUA_SEARXNG_URL", "")


def _searxng_reachable(url: str) -> bool:
    """Probe whether the SearXNG endpoint responds."""
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(
                url,
                params={"q": "test", "format": "json"},
                headers={"Accept": "application/json"},
            )
            return resp.status_code < 500
    except Exception:
        return False


@pytest.fixture
def searxng_url():
    """Return the configured SearXNG URL, skipping if unset or unreachable."""
    url = _resolve_searxng_url()
    if not url:
        pytest.skip("TINYCUA_SEARXNG_URL not set")
    if not _searxng_reachable(url):
        pytest.skip(f"SearXNG not reachable at {url}")
    return url


def test_web_search_real_returns_results(searxng_url: str) -> None:
    """A real SearXNG search returns structured results."""
    os.environ["TINYCUA_SEARXNG_URL"] = searxng_url
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("python programming language", max_results=3, timeout=15)
    assert result["success"] is True, f"search failed: {result.get('error')}"
    assert isinstance(result["results"], list)
    assert len(result["results"]) > 0
    assert "title" in result["results"][0]
    assert "url" in result["results"][0]


def test_web_search_real_blank_query(searxng_url: str) -> None:
    """Blank query still short-circuits against a real endpoint."""
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("")
    assert result["success"] is False
    assert "blank" in result["error"]