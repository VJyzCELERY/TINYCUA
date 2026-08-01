"""SearXNG-backed web search tool."""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

import httpx
from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.output_persist import SessionToolResultStore

_DEFAULT_SEARXNG_URL = "http://localhost:8080/search"
_WEB_CACHE: ContextVar[SessionToolResultStore | None] = ContextVar(
    "web_search_cache", default=None
)


def bind_web_cache(store: SessionToolResultStore | None) -> None:
    """Bind session-local web cache storage to this native tool."""
    _WEB_CACHE.set(store)


def _searxng_url() -> str:
    """Resolve the SearXNG endpoint from the environment at call time.

    Read on each call so ``.env`` loading (which happens after module import
    in the CLI flow) is honoured.
    """
    return os.environ.get("TINYCUA_SEARXNG_URL", _DEFAULT_SEARXNG_URL)


def _cached_search_result(
    cached: dict[str, Any],
    source: str,
    requested_max_results: int,
    network_error: str = "",
) -> dict[str, Any]:
    """Return a cached search result with explicit freshness provenance."""
    result = dict(cached["result"])
    cached_max_results = int(cached["key"]["max_results"])
    result["results"] = list(result["results"][: max(requested_max_results, 0)])
    result.update(
        {
            "source": source,
            "cache_id": cached["cache_id"],
            "cached_at": cached["captured_at"],
            "requested_max_results": requested_max_results,
            "cached_max_results": cached_max_results,
            "partial": cached_max_results < requested_max_results,
        }
    )
    if network_error:
        result["network_error"] = network_error
    return result


def _cache_search_result(
    result: dict[str, Any],
    store: SessionToolResultStore | None,
    query: str,
    max_results: int,
) -> dict[str, Any]:
    """Cache a search success or return compatible cached evidence after failure."""
    if result["success"] and store:
        metadata = store.cache_web(
            "web_search", {"query": query, "max_results": max_results}, result
        )
        if metadata:
            result.update(metadata)
        return result
    if (
        not result["success"]
        and store
        and (cached := store.fallback_web_search(query, max_results))
    ):
        return _cached_search_result(
            cached, "cache_fallback", max_results, str(result["error"])
        )
    return result


@tool
def web_search(
    query: str, max_results: int = 5, timeout: int = 15, load_cache: bool = False
) -> dict[str, Any]:
    """Search the web using a SearXNG endpoint.

    Args:
        query: Search query.
        max_results: Maximum number of results to return.
        timeout: Request timeout in seconds.
        load_cache: Return an exact session-cached search without a network call.

    Returns:
        Structured search results or an error dictionary.
    """
    # LLM tool calls may pass int params as strings — coerce defensively.
    try:
        max_results = int(max_results)
        timeout = int(timeout)
    except (TypeError, ValueError):
        max_results = 5
        timeout = 15
    if not isinstance(load_cache, bool):
        return {
            "success": False,
            "error": "load_cache must be a boolean",
            "results": [],
        }
    if not query.strip():
        return {"success": False, "error": "query must not be blank", "results": []}
    query = query.strip()
    store = _WEB_CACHE.get()
    if load_cache:
        if store and (
            cached := store.load_web(
                "web_search", {"query": query, "max_results": max_results}
            )
        ):
            return _cached_search_result(cached, "cache", max_results)
        return {
            "success": False,
            "error": "No matching cached search result.",
            "results": [],
        }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(
                _searxng_url(),
                params={"q": query, "format": "json"},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        result = {
            "success": False,
            "error": f"search timed out after {timeout}s",
            "results": [],
        }
    except (httpx.HTTPError, ValueError) as exc:
        result = {"success": False, "error": str(exc), "results": []}
    else:
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in data.get("results", [])[: max(max_results, 0)]
        ]
        unresponsive = data.get("unresponsive_engines") or []
        if not results and unresponsive:
            degraded = [
                entry[0] if isinstance(entry, list) else str(entry)
                for entry in unresponsive
            ]
            result = {
                "success": False,
                "error": (
                    "search backend degraded: all general-web engines "
                    f"temporarily unavailable ({', '.join(degraded)}). "
                    "Retry in 60s, reformulate the query, or try fetch_url "
                    "on a known URL instead."
                ),
                "results": [],
                "unresponsive_engines": degraded,
            }
        else:
            result = {"success": True, "query": query, "results": results}
    return _cache_search_result(result, store, query, max_results)


setattr(web_search, "bind_web_cache", bind_web_cache)
