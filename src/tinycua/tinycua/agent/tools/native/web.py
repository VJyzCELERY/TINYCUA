"""Web fetching tool.

Provides ``fetch_url`` for making HTTP requests with configurable
methods, headers, timeout, and response truncation.
"""

from __future__ import annotations

from typing import Any

import httpx
from tinycua_sdk.tools.decorators import tool


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
    try:
        with httpx.Client() as client:
            response = client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                timeout=timeout,
                follow_redirects=True,
            )

            if response.status_code >= 400:
                return {
                    "error": f"HTTP {response.status_code}: {response.reason_phrase} "
                    f"for URL: {url}"
                }

            body = response.text
            body_bytes = response.content

            if len(body_bytes) > max_size:
                truncated = body[:(max_size // 4)]  # approx bytes to chars
                return f"{truncated}\n[truncated at {max_size // 1024} KB]"

            return body

    except httpx.TimeoutException:
        return {"error": f"Request timed out after {timeout}s for URL: {url}"}
    except httpx.InvalidURL:
        return {"error": f"Invalid URL: {url}"}
    except httpx.HTTPError as exc:
        return {"error": f"HTTP error: {exc}"}
    except Exception as exc:
        return {"error": str(exc)}
