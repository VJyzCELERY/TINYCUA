"""Unit tests for web.py — mocking httpx for error codes, timeout, invalid URLs.

Milestone 5: fetch_url now returns a consistent dict shape with keys:
success, content, error, url, content_type, status.
"""

import httpx


def test_fetch_url_http_500(httpx_mock):
    """HTTP 500 returns error dict with success=False (after retries)."""
    # Register the response enough times for the retry loop (3 retries + 1).
    for _ in range(4):
        httpx_mock.add_response(
            method="GET",
            url="https://example.com/error",
            status_code=500,
            text="Internal Server Error",
        )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/error", timeout=1)
    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error"] is not None
    assert "500" in str(result["error"])


def test_fetch_url_http_403(httpx_mock):
    """HTTP 403 returns error dict with success=False."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/forbidden",
        status_code=403,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/forbidden")
    assert isinstance(result, dict)
    assert result["success"] is False
    assert "403" in str(result["error"])


def test_fetch_url_custom_method(httpx_mock):
    """Custom HTTP method (PUT) is supported — content in dict."""
    httpx_mock.add_response(
        method="PUT",
        url="https://example.com/resource",
        text="updated",
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/resource", method="PUT")
    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["content"] is not None
    assert "updated" in result["content"]


def test_fetch_url_redirect(httpx_mock):
    """Redirects are followed — content in dict."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/redirect",
        status_code=200,
        text="final destination",
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/redirect")
    assert isinstance(result, dict)
    assert result["success"] is True
    assert "final destination" in result["content"]


def test_fetch_url_empty_response(httpx_mock):
    """Empty response body returns failure (FR-072: empty body = likely JS-rendered)."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/empty",
        text="",
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/empty")
    assert isinstance(result, dict)
    # FR-072: empty body is now a failure, not a silent success.
    assert result["success"] is False
    assert "empty content" in result.get("error", "").lower()


def test_fetch_url_connection_error(httpx_mock):
    """Connection error returns error dict."""
    # Register enough exceptions for the retry loop.
    for _ in range(4):
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url="https://example.com/down",
        )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/down", timeout=1)
    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error"] is not None


def test_fetch_url_truncation_exact_boundary(httpx_mock):
    """Response exactly at max_size is not truncated."""
    body = "x" * 1024  # 1KB
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/exact",
        text=body,
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/exact", max_size=1024)
    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["content"] == body
    assert result["source_truncated"] is False


def test_fetch_url_rejects_cloudflare_challenge_header(httpx_mock):
    """Cloudflare's authoritative challenge header makes a 200 response fail."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/challenge",
        status_code=200,
        text="Requested article content",
        headers={"cf-mitigated": "challenge"},
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/challenge")

    assert result["success"] is False
    assert "challenge" in result["error"].lower()
    assert "cache_id" not in result


def test_fetch_url_rejects_human_verification_interstitial(httpx_mock):
    """A paired human-verification message is not treated as page evidence."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/challenge",
        status_code=200,
        text="Quick verification\nConfirm you're human to keep going.",
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/challenge")

    assert result["success"] is False
    assert "challenge" in result["error"].lower()


def test_fetch_url_keeps_single_human_phrase_as_content(httpx_mock):
    """One human-verification phrase alone is not enough to reject an article."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/article",
        status_code=200,
        text="This guide explains how to confirm you're human during account setup.",
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/article")

    assert result["success"] is True


def test_fetch_url_uses_cached_success_after_http_403(httpx_mock):
    """A transient fetch failure returns the exact session cache with provenance."""
    from tinycua.agent.tools.native.output_persist import SessionToolResultStore
    from tinycua.agent.tools.native.web import bind_web_cache, fetch_url

    store = SessionToolResultStore("web-cache-test")
    bind_web_cache(store)
    try:
        httpx_mock.add_response(
            method="GET",
            url="https://example.com/cached",
            text="saved",
            status_code=200,
        )
        cached = fetch_url("https://example.com/cached")
        httpx_mock.add_response(
            method="GET", url="https://example.com/cached", status_code=403
        )
        fallback = fetch_url("https://example.com/cached")
        loaded = fetch_url("https://example.com/cached", load_cache=True)

        assert cached["cache_id"]
        assert fallback["success"] is True
        assert fallback["source"] == "cache_fallback"
        assert fallback["network_error"].startswith("HTTP 403")
        assert loaded["source"] == "cache"
        assert loaded["content"] == "saved"
    finally:
        bind_web_cache(None)
        store.cleanup()


def test_fetch_url_uses_cached_success_after_challenge(httpx_mock):
    """A challenge response is rejected and replaced by prior valid evidence."""
    from tinycua.agent.tools.native.output_persist import SessionToolResultStore
    from tinycua.agent.tools.native.web import bind_web_cache, fetch_url

    store = SessionToolResultStore("web-cache-test")
    bind_web_cache(store)
    try:
        httpx_mock.add_response(
            method="GET",
            url="https://example.com/cached",
            text="saved",
            status_code=200,
        )
        cached = fetch_url("https://example.com/cached")
        httpx_mock.add_response(
            method="GET",
            url="https://example.com/cached",
            status_code=200,
            text="Quick verification\nConfirm you're human to keep going.",
        )
        fallback = fetch_url("https://example.com/cached")

        assert cached["cache_id"]
        assert fallback["success"] is True
        assert fallback["source"] == "cache_fallback"
        assert "challenge" in fallback["network_error"].lower()
        assert fallback["content"] == "saved"
    finally:
        bind_web_cache(None)
        store.cleanup()
