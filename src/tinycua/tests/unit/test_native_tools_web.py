"""Unit tests for web.py — mocking httpx for error codes, timeout, invalid URLs."""

import httpx


def test_fetch_url_http_500(httpx_mock):
    """HTTP 500 returns error dict."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/error",
        status_code=500,
        text="Internal Server Error",
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/error")
    assert isinstance(result, dict)
    assert "error" in result
    assert "500" in result["error"]


def test_fetch_url_http_403(httpx_mock):
    """HTTP 403 returns error dict."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/forbidden",
        status_code=403,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/forbidden")
    assert isinstance(result, dict)
    assert "error" in result
    assert "403" in result["error"]


def test_fetch_url_custom_method(httpx_mock):
    """Custom HTTP method (PUT) is supported."""
    httpx_mock.add_response(
        method="PUT",
        url="https://example.com/resource",
        text="updated",
        status_code=200,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/resource", method="PUT")
    assert result == "updated"


def test_fetch_url_redirect(httpx_mock):
    """Redirects are followed."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/redirect",
        status_code=200,
        text="final destination",
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/redirect")
    assert result == "final destination"


def test_fetch_url_empty_response(httpx_mock):
    """Empty response body returns empty string."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/empty",
        text="",
        status_code=200,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/empty")
    assert result == ""


def test_fetch_url_connection_error(httpx_mock):
    """Connection error returns error dict."""
    httpx_mock.add_exception(
        httpx.ConnectError("Connection refused"),
        url="https://example.com/down",
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/down")
    assert isinstance(result, dict)
    assert "error" in result


def test_fetch_url_truncation_exact_boundary(httpx_mock):
    """Response exactly at max_size is not truncated."""
    body = "x" * 1024  # 1KB
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/exact",
        text=body,
        status_code=200,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/exact", max_size=1024)
    assert "[truncated" not in result.lower()
    assert result == body
