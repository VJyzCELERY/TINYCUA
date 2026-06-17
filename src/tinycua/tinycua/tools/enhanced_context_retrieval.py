"""Scoped context cache and ReAct search for context retrieval.

Provides EnhancedContextRetrievalTool with per-invocation cache isolation
and lazy cache creation for efficient context retrieval across nodes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tinycua.config.types import Tool


class EnhancedContextRetrievalTool(Tool):
    """Tool for scoped context retrieval with per-invocation cache isolation.

    Each tool instance maintains its own cache scope. Cache files are
    lazily created on first query and reused for subsequent queries
    within the same invocation scope.
    """

    def __init__(self) -> None:
        super().__init__(name="enhanced_context_retrieval")
        self._cache: dict[str, Any] = {}
        self._workspace_dir: Path | None = None

    def bind_workspace(self, workspace_dir: str | Path | None) -> None:
        """Bind cache-file storage to a session workspace."""
        self._workspace_dir = Path(workspace_dir).resolve() if workspace_dir else None

    def _get_cache_key(self, session_context: list[dict[str, Any]]) -> str:
        """Generate a deterministic cache key from session context.

        Args:
            session_context: The session context messages.

        Returns:
            A hex digest string for use as cache key.
        """
        context_str = json.dumps(session_context, sort_keys=True, default=str)
        return hashlib.sha256(context_str.encode()).hexdigest()[:16]

    def _ensure_cache(self, session_context: list[dict[str, Any]]) -> dict[str, Any]:
        """Lazily create and return the cache for this invocation scope.

        Args:
            session_context: The session context messages.

        Returns:
            The cache dictionary for this scope.
        """
        cache_key = self._get_cache_key(session_context)
        if cache_key not in self._cache:
            cache_path = self._write_cache_file(cache_key, session_context)
            self._cache[cache_key] = {
                "context": session_context,
                "results": {},
                "cache_path": str(cache_path) if cache_path else None,
            }
        return self._cache[cache_key]

    def _write_cache_file(
        self,
        cache_key: str,
        session_context: list[dict[str, Any]],
    ) -> Path | None:
        """Persist selected context to a scoped cache file when possible."""
        if self._workspace_dir is None:
            return None
        cache_dir = self._workspace_dir / ".tinycua_context_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{cache_key}.json"
        cache_path.write_text(
            json.dumps(session_context, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return cache_path

    def __call__(
        self,
        session_context: list[dict[str, Any]] | None = None,
        query: str = "",
        page: int = 1,
        page_size: int = 5,
        **kwargs: Any,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Execute context retrieval with scoped caching.

        Args:
            session_context: The session context messages for cache scoping.
            query: The search query string.
            page: One-indexed result page to return.
            page_size: Maximum number of search hits to include in the page.
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            A dict with retrieval results from cache or fresh search.
        """
        if session_context is None:
            session_context = []

        cache = self._ensure_cache(session_context)

        # Check cache for existing results
        if query in cache["results"]:
            results = cache["results"][query]
            return self._format_results("cache", results, cache, page, page_size)

        # Perform deterministic context search and cache the result for this scope.
        results = self._react_search(session_context, query)
        cache["results"][query] = results

        return self._format_results("fresh", results, cache, page, page_size)

    def _format_results(
        self,
        source: str,
        results: list[dict[str, Any]],
        cache: dict[str, Any],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Return paginated retrieval results with cache metadata."""
        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return {
            "source": source,
            "cache_path": cache.get("cache_path"),
            "results": results[start:end],
            "page": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_results": len(results),
            },
        }

    def _react_search(
        self,
        session_context: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Perform lexical search within the session context.

        Args:
            session_context: The session context messages.
            query: The search query string.

        Returns:
            List of search result dicts.
        """
        query_terms = {
            term.lower()
            for term in query.replace("_", " ").split()
            if len(term.strip()) > 2
        }
        ranked: list[dict[str, Any]] = []
        for index, message in enumerate(session_context):
            content = message.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, sort_keys=True, default=str)
            normalized = content.lower()
            matched_terms = sorted(term for term in query_terms if term in normalized)
            score = sum(normalized.count(term) for term in matched_terms)
            if score == 0 and query_terms:
                continue
            snippet = content.strip().replace("\n", " ")[:500]
            ranked.append(
                {
                    "index": index,
                    "role": message.get("role", "unknown"),
                    "score": score,
                    "matched_terms": matched_terms,
                    "snippet": snippet,
                }
            )
        if not ranked and not query_terms:
            for index, message in enumerate(session_context[-5:]):
                content = message.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content, sort_keys=True, default=str)
                ranked.append(
                    {
                        "index": len(session_context[-5:]) - 1 + index,
                        "role": message.get("role", "unknown"),
                        "score": 0,
                        "matched_terms": [],
                        "snippet": content.strip().replace("\n", " ")[:500],
                    }
                )
        ranked.sort(key=lambda item: (-item["score"], item["index"]))
        return ranked[:5]
