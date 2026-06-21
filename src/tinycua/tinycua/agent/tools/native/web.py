"""Web fetching tool.

Provides ``fetch_url`` for making HTTP requests with configurable
methods, headers, timeout, and response truncation. HTML responses
are converted to markdown via html2text (Milestone 5 hardening).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import html2text
from tinycua_sdk.tools.decorators import tool

logger = logging.getLogger(__name__)

# Binary content-types that are not useful as text for the LLM.
_BINARY_CONTENT_TYPES = (
    "image/",
    "application/pdf",
    "application/zip",
    "application/gzip",
    "application/octet-stream",
    "application/x-tar",
    "application/x-bzip2",
    "video/",
    "audio/",
)

# Default User-Agent — httpx default is easily blocked by some sites.
_DEFAULT_USER_AGENT = "TinyCUA/1.0 (research agent; +https://github.com/tinycua)"

# Max retries for transient errors (429/5xx).
_MAX_RETRIES = 3


def _process_response(
    response: httpx.Response, max_size: int, url: str
) -> dict[str, Any]:
    """Process an HTTP response: check status, convert HTML, truncate.

    Args:
        response: The HTTP response object.
        max_size: Maximum response body size in bytes.
        url: The original URL (for error messages).

    Returns:
        A dict with success/error/content/metadata (consistent shape).
    """
    if response.status_code >= 400:
        error_msg = f"HTTP {response.status_code}"
        if response.reason_phrase:
            error_msg += f": {response.reason_phrase}"
        error_msg += f" for URL: {url}"
        return {
            "success": False,
            "error": error_msg,
            "content": None,
            "url": url,
            "content_type": response.headers.get("content-type", ""),
            "status": response.status_code,
        }

    content_type = response.headers.get("content-type", "")

    # Refuse binary content — returning mangled text is worse than a clear error.
    if any(content_type.startswith(bt) for bt in _BINARY_CONTENT_TYPES):
        return {
            "success": False,
            "error": f"binary content-type '{content_type}' not supported; use read_file for local files",
            "content": None,
            "url": url,
            "content_type": content_type,
            "status": response.status_code,
        }

    body = response.text
    body_bytes = response.content

    if len(body_bytes) > max_size:
        body = body_bytes[:max_size].decode("utf-8", errors="ignore")
        body = f"{body}\n[truncated at {max_size // 1024} KB]"

    # Convert HTML to markdown for LLM consumption.
    if "text/html" in content_type or "application/xhtml" in content_type:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # no line wrapping
        body = h.handle(body)

    return {
        "success": True,
        "content": body,
        "error": None,
        "url": url,
        "content_type": content_type,
        "status": response.status_code,
    }


@tool
def fetch_url(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    max_size: int = 102400,
) -> dict[str, Any]:
    """Fetch a URL and return its response body as markdown.

    HTML responses are converted to markdown via html2text. Binary
    content-types are refused with a clear error. Retries on 429/5xx
    with exponential backoff (max 3).

    Args:
        url: The URL to fetch.
        method: HTTP method (default: GET).
        headers: Optional HTTP headers as a dict.
        timeout: Request timeout in seconds (default: 30).
        max_size: Maximum response body size in bytes (default: 102400).

    Returns:
        Dict with keys: success, content, error, url, content_type, status.
    """
    # Add default User-Agent if not provided.
    req_headers = dict(headers or {})
    if "user-agent" not in {k.lower() for k in req_headers}:
        req_headers["User-Agent"] = _DEFAULT_USER_AGENT

    last_error: dict[str, Any] | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with httpx.Client() as client:
                response = client.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    timeout=timeout,
                    follow_redirects=True,
                )
                # Retry on 429/5xx (transient server errors).
                if response.status_code in {429, 500, 502, 503, 504} and attempt < _MAX_RETRIES:
                    import time

                    backoff = min(2**attempt, 10)
                    logger.debug(
                        "fetch_url %s got %d, retrying in %ds (attempt %d/%d)",
                        url,
                        response.status_code,
                        backoff,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    last_error = {
                        "success": False,
                        "error": f"HTTP {response.status_code} after {_MAX_RETRIES} retries for URL: {url}",
                        "content": None,
                        "url": url,
                        "content_type": response.headers.get("content-type", ""),
                        "status": response.status_code,
                    }
                    continue
                return _process_response(response, max_size, url)

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"Request timed out after {timeout}s for URL: {url}",
                "content": None,
                "url": url,
                "content_type": "",
                "status": 0,
            }
        except httpx.InvalidURL:
            return {
                "success": False,
                "error": f"Invalid URL: {url}",
                "content": None,
                "url": url,
                "content_type": "",
                "status": 0,
            }
        except httpx.HTTPError as exc:
            last_error = {
                "success": False,
                "error": f"HTTP error: {exc}",
                "content": None,
                "url": url,
                "content_type": "",
                "status": 0,
            }
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(min(2**attempt, 10))
                continue
            return last_error
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "content": None,
                "url": url,
                "content_type": "",
                "status": 0,
            }

    return last_error or {
        "success": False,
        "error": "unknown error",
        "content": None,
        "url": url,
        "content_type": "",
        "status": 0,
    }
