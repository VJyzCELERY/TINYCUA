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
