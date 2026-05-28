"""Context retrieval tools for agents."""

import uuid
from typing import Any

from tinycua_sdk.tools.decorators import tool


class ContextTools:
    """Context retrieval tools for agents."""

    def __init__(self, session_store=None, session_id=None):
        """Initialize context tools with a session store.

        Args:
            session_store: Optional SessionStore instance. If not provided,
                          uses a default SQLite store at ./tinycua.db
            session_id: Optional session ID for context operations

        """
        self._store = session_store
        self._session_id = session_id

    def _get_store(self):
        """Get or create session store."""
        if self._store is None:
            from tinycua_sdk.storage import SessionStore

            self._store = SessionStore("sqlite:///./tinycua.db")
            self._store.create_tables()
        return self._store

    def _get_current_session_id(self) -> uuid.UUID | None:
        """Get current session ID.

        Returns:
            Current session UUID from instance or None

        """
        return self._session_id

    def search_context_grep(self, query: str) -> dict[str, Any]:
        """Search session context using text matching.

        Args:
            query: Search query text

        Returns:
            {"results": [{"content": "...", "matches": N}]}

        """
        session_id = self._get_current_session_id()
        if not session_id:
            return {"error": "No active session. Set session_id first."}

        store = self._get_store()
        results = store.search_grep(session_id, query)
        return {"results": results}

    def search_context_semantic(self, query: str) -> dict[str, Any]:
        """Search session context using semantic similarity.

        Args:
            query: Search query text

        Returns:
            {"results": [{"content": "...", "score": 0.95}]}

        Note: This requires embeddings to be stored. If no embeddings
        exist, returns an error.

        """
        session_id = self._get_current_session_id()
        if not session_id:
            return {"error": "No active session. Set session_id first."}

        return {"error": "Semantic search requires embeddings. Not implemented yet."}

    def get_context_summary(self) -> dict[str, Any]:
        """Get the compacted summary of the session.

        Returns:
            {"summary": "..."} or {"error": "..."}

        """
        session_id = self._get_current_session_id()
        if not session_id:
            return {"error": "No active session. Set session_id first."}

        store = self._get_store()
        summary = store.get_summary(session_id)
        if summary is None:
            return {"summary": None, "has_summary": False}
        return {"summary": summary, "has_summary": True}

    def get_recent_turns(self, count: int = 3) -> dict[str, Any]:
        """Get the most recent turns from the session.

        Args:
            count: Number of recent turns (default 3)

        Returns:
            {"turns": [{"role": "...", "content": "..."}]}

        """
        session_id = self._get_current_session_id()
        if not session_id:
            return {"error": "No active session. Set session_id first."}

        store = self._get_store()
        turns = store.get_recent_turns(session_id, count)
        return {
            "turns": [
                {"role": t.role, "content": t.content, "turn_index": t.turn_index}
                for t in turns
            ]
        }


def search_context_grep_tool(session_store=None, session_id=None):
    """Create search_context_grep tool.

    Args:
        session_store: Optional SessionStore instance
        session_id: Optional session ID

    Returns:
        Tool instance for grep search

    """
    ctx = ContextTools(session_store, session_id)

    @tool()
    def search_context_grep(query: str) -> dict[str, Any]:
        """Search session context using text matching."""
        return ctx.search_context_grep(query)

    return search_context_grep


def search_context_semantic_tool(session_store=None, session_id=None):
    """Create search_context_semantic tool.

    Args:
        session_store: Optional SessionStore instance
        session_id: Optional session ID

    Returns:
        Tool instance for semantic search

    """
    ctx = ContextTools(session_store, session_id)

    @tool()
    def search_context_semantic(query: str) -> dict[str, Any]:
        """Search session context using semantic similarity."""
        return ctx.search_context_semantic(query)

    return search_context_semantic


def get_context_summary_tool(session_store=None, session_id=None):
    """Create get_context_summary tool.

    Args:
        session_store: Optional SessionStore instance
        session_id: Optional session ID

    Returns:
        Tool instance for getting summary

    """
    ctx = ContextTools(session_store, session_id)

    @tool()
    def get_context_summary() -> dict[str, Any]:
        """Get the compacted summary of the session."""
        return ctx.get_context_summary()

    return get_context_summary


def get_recent_turns_tool(session_store=None, session_id=None):
    """Create get_recent_turns tool.

    Args:
        session_store: Optional SessionStore instance
        session_id: Optional session ID

    Returns:
        Tool instance for getting recent turns

    """
    ctx = ContextTools(session_store, session_id)

    @tool()
    def get_recent_turns(count: int = 3) -> dict[str, Any]:
        """Get the most recent turns from the session."""
        return ctx.get_recent_turns(count)

    return get_recent_turns
