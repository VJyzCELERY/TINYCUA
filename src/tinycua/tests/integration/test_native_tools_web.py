"""Integration tests for fetch_url tool."""


def test_fetch_url_get_success(httpx_mock):
    """Successful GET request returns response body."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/data",
        text="response data",
        status_code=200,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/data")
    assert result == "response data"


def test_fetch_url_post_with_headers(httpx_mock):
    """POST request with custom headers returns response body."""
    httpx_mock.add_response(
        method="POST",
        url="https://example.com/api",
        text='{"ok": true}',
        status_code=200,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url(
        "https://example.com/api",
        method="POST",
        headers={"Authorization": "Bearer token"},
    )
    assert result == '{"ok": true}'


def test_fetch_url_http_error(httpx_mock):
    """HTTP 404 returns error dict."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/missing",
        status_code=404,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/missing")
    assert isinstance(result, dict)
    assert "error" in result
    assert "404" in result["error"]


def test_fetch_url_truncation(httpx_mock):
    """Large response is truncated with indicator."""
    large_body = "x" * 150 * 1024  # 150KB
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/large",
        text=large_body,
        status_code=200,
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/large", max_size=102400)
    assert "[truncated" in result.lower()


def test_fetch_url_timeout(httpx_mock):
    """Timeout returns error dict."""
    import httpx

    httpx_mock.add_exception(
        httpx.TimeoutException("timed out"),
        url="https://example.com/slow",
    )
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("https://example.com/slow", timeout=1)
    assert isinstance(result, dict)
    assert "error" in result


def test_fetch_url_invalid_url():
    """Invalid URL returns error dict."""
    from tinycua.tools.native.web import fetch_url

    result = fetch_url("not-a-valid-url")
    assert isinstance(result, dict)
    assert "error" in result
