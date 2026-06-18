"""SearXNG-backed web search tool."""

from __future__ import annotations

import os
from typing import Any

import httpx
from tinycua_sdk.tools.decorators import tool

_DEFAULT_SEARXNG_URL = "http://localhost:8080/search"


def _searxng_url() -> str:
    """Resolve the SearXNG endpoint from the environment at call time.

    Read on each call so ``.env`` loading (which happens after module import
    in the CLI flow) is honoured.
    """
    return os.environ.get("TINYCUA_SEARXNG_URL", _DEFAULT_SEARXNG_URL)


@tool
def web_search(query: str, max_results: int = 5, timeout: int = 15) -> dict[str, Any]:
    """Search the web using a SearXNG endpoint.

    Args:
        query: Search query.
        max_results: Maximum number of results to return.
        timeout: Request timeout in seconds.

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
    if not query.strip():
        return {"success": False, "error": "query must not be blank", "results": []}
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
        return {"success": False, "error": f"search timed out after {timeout}s", "results": []}
    except (httpx.HTTPError, ValueError) as exc:
        return {"success": False, "error": str(exc), "results": []}

    results = []
    for item in data.get("results", [])[: max(max_results, 0)]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
        )
    return {"success": True, "query": query, "results": results}
