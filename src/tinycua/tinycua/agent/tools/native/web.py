"""Web fetching tool.

Provides ``fetch_url`` for making HTTP requests with configurable
methods, headers, timeout, bounded source reads, and character pagination.
HTML responses are converted to markdown before pagination.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

import httpx
import html2text
from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.output_persist import SessionToolResultStore

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

_DEFAULT_LIMIT = 50_000
_MAX_LIMIT = 50_000
_WEB_CACHE: ContextVar[SessionToolResultStore | None] = ContextVar(
    "fetch_url_web_cache", default=None
)


def bind_web_cache(store: SessionToolResultStore | None) -> None:
    """Bind session-local web cache storage to this native tool."""
    _WEB_CACHE.set(store)


def _fetch_cache_key(
    url: str, method: str, headers: dict[str, str], max_size: int
) -> dict[str, Any]:
    """Return the exact cache key for a fetch request."""
    return {
        "url": url,
        "method": method.upper(),
        "headers": tuple(
            sorted((key.lower(), value) for key, value in headers.items())
        ),
        "max_size": max_size,
    }


def _page_metadata(
    offset: Any,
    limit: Any,
    *,
    returned_chars: int = 0,
    total_chars: int = 0,
    source_truncated: bool = False,
    final_url: str,
) -> dict[str, Any]:
    """Build consistent character-page metadata."""
    has_more = (
        isinstance(offset, int)
        and not isinstance(offset, bool)
        and offset + returned_chars < total_chars
    )
    return {
        "offset": offset,
        "limit": limit,
        "returned_chars": returned_chars,
        "total_chars": total_chars,
        "truncated": has_more,
        "source_truncated": source_truncated,
        "next_offset": offset + returned_chars if has_more else None,
        "final_url": final_url,
    }


def _error_result(
    error: str,
    url: str,
    offset: Any,
    limit: Any,
    *,
    content: str | None = None,
    content_type: str = "",
    status: int = 0,
    source_truncated: bool = False,
    final_url: str | None = None,
) -> dict[str, Any]:
    """Return the stable fetch error shape."""
    return {
        "success": False,
        "error": error,
        "content": content,
        "url": url,
        "content_type": content_type,
        "status": status,
        **_page_metadata(
            offset,
            limit,
            source_truncated=source_truncated,
            final_url=final_url or url,
        ),
    }


def _process_response(
    response: httpx.Response,
    max_size: int,
    url: str,
    offset: int = 0,
    limit: int = _DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Process an HTTP response and page its model-visible content.

    Args:
        response: The HTTP response object.
        max_size: Maximum response body size in bytes.
        url: The original URL (for error messages).
        offset: Character offset into converted output.
        limit: Maximum converted characters to return.

    Returns:
        A dict with success/error/content/metadata (consistent shape).
    """
    try:
        final_url = str(response.url) or url
    except (AttributeError, RuntimeError):
        final_url = url

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        error_msg = f"HTTP {response.status_code}"
        if response.reason_phrase:
            error_msg += f": {response.reason_phrase}"
        error_msg += f" for URL: {url}"
        return _error_result(
            error_msg,
            url,
            offset,
            limit,
            content_type=content_type,
            status=response.status_code,
            final_url=final_url,
        )

    # Refuse binary content — returning mangled text is worse than a clear error.
    if any(content_type.startswith(bt) for bt in _BINARY_CONTENT_TYPES):
        return _error_result(
            f"binary content-type '{content_type}' not supported; use read_file for local files",
            url,
            offset,
            limit,
            content_type=content_type,
            status=response.status_code,
            final_url=final_url,
        )

    body = response.text
    body_bytes = response.content
    source_truncated = len(body_bytes) > max_size

    if source_truncated:
        body = body_bytes[:max_size].decode(
            response.encoding or "utf-8", errors="ignore"
        )

    # Convert HTML to markdown for LLM consumption.
    if "text/html" in content_type or "application/xhtml" in content_type:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # no line wrapping
        body = h.handle(body)

    # FR-072: detect empty bodies (JS-rendered pages, auth-walled, etc.)
    # and return failure so the model knows to try a different source.
    if not body or not body.strip():
        return _error_result(
            (
                "Page returned empty content (likely JS-rendered or "
                "requires authentication). Cannot verify content. Try a "
                "different source or use web_search for snippets."
            ),
            url,
            offset,
            limit,
            content="",
            content_type=content_type,
            status=response.status_code,
            source_truncated=source_truncated,
            final_url=final_url,
        )

    total_chars = len(body)
    content = body[offset : offset + limit]
    returned_chars = len(content)

    return {
        "success": True,
        "content": content,
        "error": None,
        "url": url,
        "content_type": content_type,
        "status": response.status_code,
        **_page_metadata(
            offset,
            limit,
            returned_chars=returned_chars,
            total_chars=total_chars,
            source_truncated=source_truncated,
            final_url=final_url,
        ),
        "_cache_content": body,
    }


def _cached_fetch_result(
    cached: dict[str, Any],
    offset: int,
    limit: int,
    source: str,
    network_error: str = "",
) -> dict[str, Any]:
    """Render a requested page from one cached full fetch response."""
    payload = cached["result"]
    content = str(payload["content"])
    page = content[offset : offset + limit]
    result = {
        "success": True,
        "content": page,
        "error": None,
        "url": payload["url"],
        "content_type": payload["content_type"],
        "status": payload["status"],
        **_page_metadata(
            offset,
            limit,
            returned_chars=len(page),
            total_chars=len(content),
            source_truncated=bool(payload["source_truncated"]),
            final_url=payload["final_url"],
        ),
        "source": source,
        "cache_id": cached["cache_id"],
        "cached_at": cached["captured_at"],
    }
    if network_error:
        result["network_error"] = network_error
    return result


def _cache_fetch_result(
    result: dict[str, Any],
    store: SessionToolResultStore | None,
    key: dict[str, Any],
    offset: int,
    limit: int,
) -> dict[str, Any]:
    """Cache a network success or use exact cached evidence after failure."""
    full_content = result.pop("_cache_content", None)
    if result.get("success") is True and isinstance(full_content, str) and store:
        metadata = store.cache_web(
            "fetch_url",
            key,
            {
                "content": full_content,
                "url": result["url"],
                "content_type": result["content_type"],
                "status": result["status"],
                "source_truncated": result["source_truncated"],
                "final_url": result["final_url"],
            },
        )
        if metadata:
            result.update(metadata)
        return result
    if (
        result.get("success") is False
        and store
        and (cached := store.load_web("fetch_url", key))
    ):
        return _cached_fetch_result(
            cached, offset, limit, "cache_fallback", str(result["error"])
        )
    return result


@tool
def fetch_url(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    max_size: int = 102400,
    offset: int = 0,
    limit: int = _DEFAULT_LIMIT,
    load_cache: bool = False,
) -> dict[str, Any]:
    """Fetch a character page of a URL's model-visible content.

    HTML is converted to markdown before character pagination. ``max_size``
    bounds source bytes independently of the model-visible ``limit``.
    ``truncated`` means more converted characters follow the page, while
    ``source_truncated`` means ``max_size`` cut the source. ``total_chars``
    counts converted characters from that bounded source. Binary content-types
    are refused. Retries 429/5xx with exponential backoff.

    Args:
        url: The URL to fetch.
        method: HTTP method (default: GET).
        headers: Optional HTTP headers as a dict.
        timeout: Request timeout in seconds (default: 30).
        max_size: Maximum response body size in bytes (default: 102400).
        offset: Zero-based character offset into converted output (default: 0).
        limit: Characters to return, from 1 through 50000 (default: 50000).
        load_cache: Return an exact session-cached response without a network call.

    Returns:
        Dict preserving success, content, error, url, content_type, and status,
        plus offset, limit, returned_chars, total_chars, truncated,
        source_truncated, next_offset, and final_url.
    """
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return _error_result(
            "offset must be a non-negative integer", url, offset, limit
        )
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= _MAX_LIMIT
    ):
        return _error_result(
            f"limit must be an integer from 1 through {_MAX_LIMIT}",
            url,
            offset,
            limit,
        )
    if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size < 1:
        return _error_result("max_size must be a positive integer", url, offset, limit)
    if not isinstance(load_cache, bool):
        return _error_result("load_cache must be a boolean", url, offset, limit)

    # Add default User-Agent if not provided.
    req_headers = dict(headers or {})
    if "user-agent" not in {k.lower() for k in req_headers}:
        req_headers["User-Agent"] = _DEFAULT_USER_AGENT
    key = _fetch_cache_key(url, method, req_headers, max_size)
    store = _WEB_CACHE.get()
    if load_cache:
        if store and (cached := store.load_web("fetch_url", key)):
            return _cached_fetch_result(cached, offset, limit, "cache")
        return _error_result("No matching cached fetch result.", url, offset, limit)

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
                if (
                    response.status_code in {429, 500, 502, 503, 504}
                    and attempt < _MAX_RETRIES
                ):
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
                    last_error = _error_result(
                        f"HTTP {response.status_code} after {_MAX_RETRIES} retries for URL: {url}",
                        url,
                        offset,
                        limit,
                        content_type=response.headers.get("content-type", ""),
                        status=response.status_code,
                        final_url=str(response.url),
                    )
                    continue
                return _cache_fetch_result(
                    _process_response(response, max_size, url, offset, limit),
                    store,
                    key,
                    offset,
                    limit,
                )

        except httpx.TimeoutException:
            return _cache_fetch_result(
                _error_result(
                    f"Request timed out after {timeout}s for URL: {url}",
                    url,
                    offset,
                    limit,
                ),
                store,
                key,
                offset,
                limit,
            )
        except httpx.InvalidURL:
            return _cache_fetch_result(
                _error_result(f"Invalid URL: {url}", url, offset, limit),
                store,
                key,
                offset,
                limit,
            )
        except httpx.HTTPError as exc:
            last_error = _error_result(f"HTTP error: {exc}", url, offset, limit)
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(min(2**attempt, 10))
                continue
            return _cache_fetch_result(last_error, store, key, offset, limit)
        except Exception as exc:
            return _cache_fetch_result(
                _error_result(str(exc), url, offset, limit),
                store,
                key,
                offset,
                limit,
            )

    return _cache_fetch_result(
        last_error or _error_result("unknown error", url, offset, limit),
        store,
        key,
        offset,
        limit,
    )


setattr(fetch_url, "bind_web_cache", bind_web_cache)
