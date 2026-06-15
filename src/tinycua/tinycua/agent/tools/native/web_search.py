"""SearXNG-backed web search tool."""

from __future__ import annotations

from typing import Any

import httpx
from tinycua_sdk.tools.decorators import tool

_SEARXNG_URL = "https://searxng.salmon-crested.ts.net/search"


@tool
def web_search(query: str, max_results: int = 5, timeout: int = 15) -> dict[str, Any]:
    """Search the web using the public SearXNG endpoint.

    Args:
        query: Search query.
        max_results: Maximum number of results to return.
        timeout: Request timeout in seconds.

    Returns:
        Structured search results or an error dictionary.
    """
    if not query.strip():
        return {"success": False, "error": "query must not be blank", "results": []}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(
                _SEARXNG_URL,
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
