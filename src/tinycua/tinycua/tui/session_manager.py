"""Session management for TinyCUA TUI."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from tinycua_sdk.storage.store import get_session_store

if TYPE_CHECKING:
    from tinycua_sdk.storage.models import Session
    from tinycua_sdk.storage.store import SessionStore

logger = logging.getLogger(__name__)


class TuiSessionManager:
    """Session manager for TUI sessions.

    Provides session CRUD operations and manages current
    session state for the TUI.
    """

    def __init__(self, store: SessionStore | None) -> None:
        """Initialize session manager.

        Args:
            store: Optional SessionStore instance. If None, will be
                created lazily.
        """
        self._store = store
        self._current_session_id: uuid.UUID | None = None
        self._sessions: list[Any] = []

    def _get_store(self) -> SessionStore:
        """Get or create the session store.

        Returns:
            SessionStore instance.
        """
        if self._store is None:
            try:
                self._store = get_session_store()
            except Exception:
                logger.exception("Failed to get session store")
                raise
        return self._store

    def create_session(self, name: str) -> Session | None:
        """Create a new session.

        Args:
            name: Session name.

        Returns:
            Created Session or None on error.
        """
        store = self._get_store()
        try:
            session = store.create_session(name)
            self._current_session_id = session.id
        except Exception:
            logger.exception("Failed to create session")
            return None
        else:
            return session

    def list_sessions(self) -> list[Session]:
        """List all sessions.

        Returns:
            List of Session instances.
        """
        store = self._get_store()
        try:
            sessions = store.list_sessions()
            self._sessions = sessions
        except Exception:
            logger.exception("Failed to list sessions")
            return []
        else:
            return sessions

    def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session.

        Args:
            session_id: Session UUID.

        Returns:
            True if deleted, False otherwise.
        """
        store = self._get_store()
        try:
            result = store.delete_session(session_id)
            if self._current_session_id == session_id:
                self._current_session_id = None
        except Exception:
            logger.exception("Failed to delete session")
            return False
        else:
            return result

    def set_current_session(self, session_id: uuid.UUID) -> None:
        """Set the current session.

        Args:
            session_id: Session UUID.
        """
        self._current_session_id = session_id

    def get_current_session(self) -> Session | None:
        """Get the current session.

        Returns:
            Current Session or None.
        """
        if self._current_session_id is None:
            return None
        store = self._get_store()
        try:
            return store.get_session(self._current_session_id)
        except Exception:
            logger.exception("Failed to get current session")
            return None

    def resume_session(self, session_id: uuid.UUID) -> Session | None:
        """Resume a session.

        Args:
            session_id: Session UUID to resume.

        Returns:
            Session if found, None otherwise.
        """
        store = self._get_store()
        try:
            session = store.get_session(session_id)
            if session:
                self._current_session_id = session_id
        except Exception:
            logger.exception("Failed to resume session")
            return None
        else:
            return session

    def get_current_session_id(self) -> uuid.UUID | None:
        """Get current session ID.

        Returns:
            Current session UUID or None.
        """
        return self._current_session_id
