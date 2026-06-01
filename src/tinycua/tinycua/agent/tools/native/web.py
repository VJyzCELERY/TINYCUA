"""Web fetching tool.

Provides ``fetch_url`` for making HTTP requests with configurable
methods, headers, timeout, and response truncation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from tinycua_sdk.tools.decorators import Tool, tool

if TYPE_CHECKING:
    from tinycua.agent.tools.context import ExecutorContext


_HTTP_CLIENT: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(timeout=10.0)
    return _HTTP_CLIENT


def _process_response(response: httpx.Response, max_size: int, url: str) -> str | dict[str, Any]:
    """Process an HTTP response: check status, truncate if needed.

    Args:
        response: The HTTP response object.
        max_size: Maximum response body size in bytes.
        url: The original URL (for error messages).

    Returns:
        The response body as a string on success, or an error dict on failure.
    """
    if response.status_code >= 400:
        error_msg = f"HTTP {response.status_code}"
        if response.reason_phrase:
            error_msg += f": {response.reason_phrase}"
        error_msg += f" for URL: {url}"
        return {"error": error_msg}

    body = response.text
    body_bytes = response.content

    if len(body_bytes) > max_size:
        truncated = body_bytes[:max_size].decode("utf-8", errors="ignore")
        return f"{truncated}\n[truncated at {max_size // 1024} KB]"

    return body


@tool
def fetch_url(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    max_size: int = 102400,
) -> str | dict[str, Any]:
    """Fetch a URL and return its response body.

    Args:
        url: The URL to fetch.
        method: HTTP method (default: GET).
        headers: Optional HTTP headers as a dict.
        timeout: Request timeout in seconds (default: 30).
        max_size: Maximum response body size in bytes (default: 102400).

    Returns:
        The response body as a string on success, or an error dict on failure.
    """
    return _execute_fetch(url, method, headers, timeout, max_size)


def _execute_fetch(
    url: str,
    method: str,
    headers: dict[str, str] | None,
    timeout: int,
    max_size: int,
) -> str | dict[str, Any]:
    """Core HTTP fetch logic shared by ``fetch_url`` and factory tools."""
    try:
        client = _get_client()
        response = client.request(
            method=method.upper(),
            url=url,
            headers=headers or {},
            timeout=timeout,
            follow_redirects=True,
        )
        return _process_response(response, max_size, url)

    except httpx.TimeoutException:
        return {"error": f"Request timed out after {timeout}s for URL: {url}"}
    except httpx.InvalidURL:
        return {"error": f"Invalid URL: {url}"}
    except httpx.HTTPError as exc:
        return {"error": f"HTTP error: {exc}"}
    except Exception as exc:
        return {"error": str(exc)}


def create_fetch_url(context: ExecutorContext) -> Tool:
    """Create a ``fetch_url`` tool bound to the given *context*.

    Uses ``context.config.fetch_timeout``, ``context.config.max_fetch_size``,
    and checks ``context.config.enable_fetch`` feature flag.
    """
    def _execute(
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        max_size: int = 102400,
    ) -> str | dict[str, Any]:
        if not context.config.enable_fetch:
            return {"error": "fetch_url is disabled by executor configuration (enable_fetch=False)"}
        effective_timeout = min(timeout, context.config.fetch_timeout)
        effective_max_size = min(max_size, context.config.max_fetch_size)
        return _execute_fetch(url, method, headers, effective_timeout, effective_max_size)

    return Tool.from_callable(_execute, name="fetch_url")


__all__ = [
    "create_fetch_url",
    "fetch_url",
]
