"""Unit tests for web_search.py — env var resolution, mocked SearXNG responses."""

from __future__ import annotations

import os

import httpx
import pytest


@pytest.fixture(autouse=True)
def _isolate_searxng_env(monkeypatch):
    """Ensure TINYCUA_SEARXNG_URL does not leak between tests."""
    monkeypatch.delenv("TINYCUA_SEARXNG_URL", raising=False)
    yield


def test_web_search_blank_query_returns_error_without_network() -> None:
    """Blank query short-circuits before any HTTP call."""
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("   ")
    assert result == {
        "success": False,
        "error": "query must not be blank",
        "results": [],
    }


def test_web_search_uses_env_var_url(httpx_mock) -> None:
    """TINYCUA_SEARXNG_URL overrides the default endpoint."""
    httpx_mock.add_response(
        method="GET",
        url="https://custom.example.com/search?q=test&format=json",
        json={"results": []},
    )
    os.environ["TINYCUA_SEARXNG_URL"] = "https://custom.example.com/search"
    try:
        from tinycua.agent.tools.native.web_search import web_search

        result = web_search("test")
        assert result["success"] is True
    finally:
        del os.environ["TINYCUA_SEARXNG_URL"]


def test_web_search_defaults_to_localhost(httpx_mock) -> None:
    """When env var is unset, the default localhost URL is used."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=hello&format=json",
        json={"results": []},
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("hello")
    assert result["success"] is True


def test_web_search_parses_results(httpx_mock) -> None:
    """Successful search returns parsed results with title/url/content."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=python&format=json",
        json={
            "results": [
                {
                    "title": "Python",
                    "url": "https://python.org",
                    "content": "Python language",
                },
                {
                    "title": "PyPI",
                    "url": "https://pypi.org",
                    "content": "Package index",
                },
            ]
        },
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("python", max_results=5)
    assert result["success"] is True
    assert result["query"] == "python"
    assert len(result["results"]) == 2
    assert result["results"][0] == {
        "title": "Python",
        "url": "https://python.org",
        "content": "Python language",
    }


def test_web_search_empty_results(httpx_mock) -> None:
    """Empty results list returns success with empty list."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=nothing&format=json",
        json={"results": []},
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("nothing")
    assert result["success"] is True
    assert result["results"] == []


def test_web_search_max_results_limits_output(httpx_mock) -> None:
    """max_results truncates the returned list."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=test&format=json",
        json={
            "results": [{"title": str(i), "url": "", "content": ""} for i in range(10)]
        },
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("test", max_results=3)
    assert len(result["results"]) == 3


def test_web_search_connection_error(httpx_mock) -> None:
    """Connection error (no SearXNG running) returns error dict."""
    httpx_mock.add_exception(
        httpx.ConnectError("Connection refused"),
        url="http://localhost:8080/search?q=fail&format=json",
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("fail")
    assert result["success"] is False
    assert "Connection refused" in result["error"]
    assert result["results"] == []


def test_web_search_timeout(httpx_mock) -> None:
    """Timeout returns a timeout-specific error dict."""
    httpx_mock.add_exception(
        httpx.TimeoutException("timed out"),
        url="http://localhost:8080/search?q=slow&format=json",
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("slow", timeout=1)
    assert result["success"] is False
    assert "timed out" in result["error"]


def test_web_search_coerces_string_params(httpx_mock) -> None:
    """LLM tool calls may pass int params as strings — coerce defensively."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=test&format=json",
        json={
            "results": [{"title": str(i), "url": "", "content": ""} for i in range(10)]
        },
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("test", max_results="3", timeout="15")
    assert result["success"] is True
    assert len(result["results"]) == 3


def test_web_search_empty_results_with_degraded_engines(httpx_mock) -> None:
    """Empty results + unresponsive_engines → distinct backend-degraded error.

    The model must distinguish "genuinely no hits" from "search backend is
    degraded" so it retries/waits instead of concluding the topic is absent.
    """
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=niche+topic&format=json",
        json={
            "results": [],
            "unresponsive_engines": [
                ["brave", "Suspended: too many requests"],
                ["google", "Suspended: CAPTCHA"],
            ],
        },
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("niche topic")
    assert result["success"] is False
    assert "degraded" in result["error"]
    assert result["results"] == []
    assert result["unresponsive_engines"] == ["brave", "google"]


def test_web_search_empty_results_no_unresponsive_field(httpx_mock) -> None:
    """Empty results with no unresponsive_engines → success=True (genuine no-hits)."""
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:8080/search?q=zzz+no+match&format=json",
        json={"results": []},
    )
    from tinycua.agent.tools.native.web_search import web_search

    result = web_search("zzz no match")
    assert result["success"] is True
    assert result["results"] == []


def test_web_search_falls_back_to_compatible_cached_result(httpx_mock) -> None:
    """A failed broader search exposes a labeled prior same-query result."""
    from tinycua.agent.tools.native.output_persist import SessionToolResultStore
    from tinycua.agent.tools.native.web_search import bind_web_cache, web_search

    store = SessionToolResultStore("web-cache-test")
    bind_web_cache(store)
    try:
        httpx_mock.add_response(
            method="GET",
            url="http://localhost:8080/search?q=eggs&format=json",
            json={
                "results": [{"title": "Eggs", "url": "https://eg.gs", "content": "x"}]
            },
        )
        cached = web_search("eggs", max_results=5)
        httpx_mock.add_exception(
            httpx.ConnectError("rate limited"),
            url="http://localhost:8080/search?q=eggs&format=json",
        )
        fallback = web_search("eggs", max_results=15)
        missing = web_search("eggs", max_results=15, load_cache=True)

        assert cached["cache_id"]
        assert fallback["success"] is True
        assert fallback["source"] == "cache_fallback"
        assert fallback["cached_max_results"] == 5
        assert fallback["partial"] is True
        assert missing["success"] is False
        assert "cache" in missing["error"].lower()
    finally:
        bind_web_cache(None)
        store.cleanup()
