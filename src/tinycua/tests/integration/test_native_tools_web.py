"""Integration tests for fetch_url tool."""

import httpx
import pytest


_CORE_KEYS = {"success", "content", "error", "url", "content_type", "status"}
_PAGE_KEYS = {
    "offset",
    "limit",
    "returned_chars",
    "total_chars",
    "truncated",
    "source_truncated",
    "next_offset",
    "final_url",
}


def test_fetch_url_get_success(httpx_mock):
    """Successful GET request returns response body and page metadata."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/data",
        text="response data",
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/data")
    assert result["content"] == "response data"
    assert result["success"] is True
    assert _CORE_KEYS | _PAGE_KEYS <= result.keys()
    assert result["offset"] == 0
    assert result["limit"] == 50_000
    assert result["returned_chars"] == result["total_chars"] == 13
    assert result["truncated"] is False
    assert result["source_truncated"] is False
    assert result["next_offset"] is None
    assert result["final_url"] == "https://example.com/data"


def test_fetch_url_post_with_headers(httpx_mock):
    """POST request with custom headers returns response body."""
    httpx_mock.add_response(
        method="POST",
        url="https://example.com/api",
        text='{"ok": true}',
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url(
        "https://example.com/api",
        method="POST",
        headers={"Authorization": "Bearer token"},
    )
    assert result["content"] == '{"ok": true}'


def test_fetch_url_http_error(httpx_mock):
    """HTTP 404 preserves core fields and returns empty page metadata."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/missing",
        status_code=404,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/missing")
    assert _CORE_KEYS | _PAGE_KEYS <= result.keys()
    assert "404" in result["error"]
    assert result["returned_chars"] == result["total_chars"] == 0
    assert result["truncated"] is False
    assert result["source_truncated"] is False
    assert result["next_offset"] is None


def test_fetch_url_source_and_page_truncation_are_independent(httpx_mock):
    """Source bytes and model-visible characters have separate metadata."""
    large_body = "x" * 150 * 1024  # 150KB
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/large",
        text=large_body,
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url(
        "https://example.com/large", max_size=102_400, offset=10, limit=20
    )
    assert result["content"] == "x" * 20
    assert result["returned_chars"] == 20
    assert result["total_chars"] == 102_400
    assert result["truncated"] is True
    assert result["source_truncated"] is True
    assert result["next_offset"] == 30


def test_fetch_url_timeout(httpx_mock):
    """Timeout returns error dict."""
    httpx_mock.add_exception(
        httpx.TimeoutException("timed out"),
        url="https://example.com/slow",
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/slow", timeout=1)
    assert result["success"] is False
    assert _CORE_KEYS | _PAGE_KEYS <= result.keys()


def test_fetch_url_invalid_url():
    """Invalid URL returns error dict."""
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("not-a-valid-url")
    assert result["success"] is False
    assert _CORE_KEYS | _PAGE_KEYS <= result.keys()


def test_fetch_url_paginates_html_after_markdown_conversion(httpx_mock):
    """Character offsets address converted Markdown, not source HTML."""
    html = "<html><body><h1>Title</h1><p>abcdef</p></body></html>"
    for _ in range(2):
        httpx_mock.add_response(
            url="https://example.com/page", text=html, headers={"content-type": "text/html"}
        )
    from tinycua.agent.tools.native.web import fetch_url

    full = fetch_url("https://example.com/page", limit=50_000)
    page = fetch_url("https://example.com/page", offset=3, limit=5)

    assert "<h1>" not in full["content"]
    assert page["content"] == full["content"][3:8]
    assert page["total_chars"] == len(full["content"])
    assert page["returned_chars"] == 5
    assert page["next_offset"] == 8


def test_fetch_url_paginates_unicode_by_character(httpx_mock):
    """A page boundary does not split a multibyte character."""
    httpx_mock.add_response(url="https://example.com/unicode", text="A🙂BC")
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/unicode", limit=2)

    assert result["content"] == "A🙂"
    assert result["returned_chars"] == 2
    assert result["total_chars"] == 4
    assert result["next_offset"] == 2


def test_fetch_url_source_limit_does_not_split_multibyte_character(httpx_mock):
    """An incomplete final source code point is omitted rather than mangled."""
    httpx_mock.add_response(
        url="https://example.com/source-unicode",
        content="ééé".encode(),
        headers={"content-type": "text/plain; charset=utf-8"},
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/source-unicode", max_size=5)

    assert result["content"] == "éé"
    assert result["total_chars"] == 2
    assert result["source_truncated"] is True
    assert result["truncated"] is False


def test_fetch_url_redirect_reports_original_and_final_urls(httpx_mock):
    """Redirects retain the requested URL and expose the final URL."""
    httpx_mock.add_response(
        url="https://example.com/redirect",
        status_code=302,
        headers={"location": "https://example.com/final"},
    )
    httpx_mock.add_response(url="https://example.com/final", text="final")
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/redirect")

    assert result["url"] == "https://example.com/redirect"
    assert result["final_url"] == "https://example.com/final"
    assert result["content"] == "final"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"offset": -1}, "offset"),
        ({"offset": "invalid"}, "offset"),
        ({"limit": 0}, "limit"),
        ({"limit": 50_001}, "limit"),
        ({"limit": "invalid"}, "limit"),
        ({"max_size": 0}, "max_size"),
    ],
)
def test_fetch_url_rejects_invalid_page_bounds(kwargs, message):
    """Invalid character page bounds fail before transport."""
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/data", **kwargs)

    assert result["success"] is False
    assert message in result["error"].lower()
    assert _CORE_KEYS | _PAGE_KEYS <= result.keys()


def test_fetch_url_out_of_range_offset_returns_empty_final_page(httpx_mock):
    """An offset beyond converted output is a successful exhausted page."""
    httpx_mock.add_response(url="https://example.com/short", text="short")
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/short", offset=10, limit=5)

    assert result["success"] is True
    assert result["content"] == ""
    assert result["returned_chars"] == 0
    assert result["total_chars"] == 5
    assert result["truncated"] is False
    assert result["next_offset"] is None


@pytest.mark.parametrize(
    ("content_type", "content", "error_text"),
    [
        ("text/html", b"", "empty content"),
        ("image/png", b"PNG_DATA", "binary"),
    ],
)
def test_fetch_url_non_model_content_has_metadata(
    httpx_mock, content_type, content, error_text
):
    """Empty and binary responses fail without dropping pagination metadata."""
    httpx_mock.add_response(
        url="https://example.com/unusable",
        content=content,
        headers={"content-type": content_type},
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/unusable", offset=2, limit=4)

    assert result["success"] is False
    assert error_text in result["error"].lower()
    assert result["offset"] == 2
    assert result["limit"] == 4
    assert result["returned_chars"] == result["total_chars"] == 0
    assert result["final_url"] == "https://example.com/unusable"
