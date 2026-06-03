"""Web fetching tool.

Provides ``fetch_url`` for making HTTP requests with configurable
methods, headers, timeout, and response truncation.
"""

from typing import Any

import httpx
from tinycua_sdk.tools.decorators import tool


def _process_response(
    response: httpx.Response, max_size: int, url: str
) -> str | dict[str, Any]:
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
    # Input validation
    if not isinstance(url, str):
        return {"error": f"Invalid url type: expected str, got {type(url).__name__}"}
    if not isinstance(method, str):
        return {"error": f"Invalid method type: expected str, got {type(method).__name__}"}
    if not isinstance(headers, dict | type(None)):
        return {"error": f"Invalid headers type: expected dict or None, got {type(headers).__name__}"}
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        return {"error": f"Invalid timeout: {timeout}. Must be a positive number."}
    if not isinstance(max_size, int) or max_size < 0:
        return {"error": f"Invalid max_size: {max_size}. Must be a non-negative integer."}

    try:
        with httpx.Client() as client:
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
