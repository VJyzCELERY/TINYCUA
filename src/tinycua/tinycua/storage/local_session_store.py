"""Local session store for TinyCUA."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from tinycua_sdk.storage.models import Session
from tinycua_sdk.storage.store import SessionStore

logger = logging.getLogger(__name__)


class LocalSessionStore:
    """Local session store using SQLite.

    Provides session and message CRUD operations using
    the SDK's SessionStore with local SQLite database.
    """

    def __init__(self, store: SessionStore) -> None:
        """Initialize the local session store.

        Args:
            store: SessionStore instance.
        """
        self._store = store

    @property
    def store(self) -> SessionStore:
        """Get the underlying session store.

        Returns:
            SessionStore instance.
        """
        return self._store

    def create_session(
        self,
        name: str,
        user_id: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> Optional[Session]:
        """Create a new session.

        Args:
            name: Session name.
            user_id: Optional user ID.
            session_id: Optional session UUID to preserve.

        Returns:
            Created Session or None on error.
        """
        try:
            return self._store.create_session(
                name=name, user_id=user_id, session_id=session_id
            )
        except Exception:
            logger.exception("Failed to create session")
            return None

    def get_session(self, session_id: uuid.UUID) -> Optional[Session]:
        """Get a session by ID.

        Args:
            session_id: Session UUID.

        Returns:
            Session if found, None otherwise.
        """
        try:
            return self._store.get_session(session_id)
        except Exception:
            logger.exception("Failed to get session")
            return None

    def get_session_by_name(self, name: str) -> Optional[Session]:
        """Get a session by name.

        Args:
            name: Session name.

        Returns:
            Session if found, None otherwise.
        """
        try:
            return self._store.get_session_by_name(name)
        except Exception:
            logger.exception("Failed to get session by name")
            return None

    def list_sessions(self, user_id: Optional[str] = None) -> list:
        """List all sessions.

        Args:
            user_id: Optional user ID to filter by.

        Returns:
            List of Session instances.
        """
        try:
            return self._store.list_sessions(user_id=user_id)
        except Exception:
            logger.exception("Failed to list sessions")
            return []

    def update_session(self, session_id: uuid.UUID, **kwargs) -> Optional[Session]:
        """Update a session.

        Args:
            session_id: Session UUID.
            **kwargs: Fields to update.

        Returns:
            Updated Session if found, None otherwise.
        """
        try:
            return self._store.update_session(session_id, **kwargs)
        except Exception:
            logger.exception("Failed to update session")
            return None

    def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session.

        Args:
            session_id: Session UUID.

        Returns:
            True if deleted, False if not found.
        """
        try:
            return self._store.delete_session(session_id)
        except Exception:
            logger.exception("Failed to delete session")
            return False

    def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        reasoning: Optional[str] = None,
    ) -> Optional[object]:
        """Add a message to a session.

        Args:
            session_id: Session UUID.
            role: Message role (user/assistant/tool).
            content: Message content.
            reasoning: Optional agent reasoning.

        Returns:
            Created Message if session exists, None otherwise.
        """
        try:
            return self._store.add_message(
                session_id=session_id,
                role=role,
                content=content,
                reasoning=reasoning,
            )
        except Exception:
            logger.exception("Failed to add message")
            return None

    def get_messages(self, session_id: uuid.UUID, limit: Optional[int] = None) -> list:
        """Get messages for a session.

        Args:
            session_id: Session UUID.
            limit: Optional limit.

        Returns:
            List of Message instances.
        """
        try:
            return self._store.get_messages(session_id, limit=limit)
        except Exception:
            logger.exception("Failed to get messages")
            return []

    def get_recent_turns(self, session_id: uuid.UUID, count: int = 3) -> list:
        """Get recent non-archived turns.

        Args:
            session_id: Session UUID.
            count: Number of recent turns.

        Returns:
            List of recent Message instances.
        """
        try:
            return self._store.get_recent_turns(session_id, count=count)
        except Exception:
            logger.exception("Failed to get recent turns")
            return []
