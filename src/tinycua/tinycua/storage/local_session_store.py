"""Local session store for TinyCUA."""

from __future__ import annotations

import logging
import uuid

from tinycua.exceptions import StorageError
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
        user_id: str | None = None,
        session_id: uuid.UUID | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            name: Session name.
            user_id: Optional user ID.
            session_id: Optional session UUID to preserve.

        Returns:
            Created Session.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.create_session(
                name=name, user_id=user_id, session_id=session_id
            )
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to create session: {exc}") from exc

    def get_session(self, session_id: uuid.UUID) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session UUID.

        Returns:
            Session if found, None otherwise.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.get_session(session_id)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to get session: {exc}") from exc

    def get_session_by_name(self, name: str) -> Session | None:
        """Get a session by name.

        Args:
            name: Session name.

        Returns:
            Session if found, None otherwise.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.get_session_by_name(name)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to get session by name: {exc}") from exc

    def list_sessions(self, user_id: str | None = None) -> list:
        """List all sessions.

        Args:
            user_id: Optional user ID to filter by.

        Returns:
            List of Session instances.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.list_sessions(user_id=user_id)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to list sessions: {exc}") from exc

    def update_session(self, session_id: uuid.UUID, **kwargs) -> Session | None:
        """Update a session.

        Args:
            session_id: Session UUID.
            **kwargs: Fields to update.

        Returns:
            Updated Session if found, None otherwise.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.update_session(session_id, **kwargs)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to update session: {exc}") from exc

    def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session.

        Args:
            session_id: Session UUID.

        Returns:
            True if deleted, False if not found.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.delete_session(session_id)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to delete session: {exc}") from exc

    def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        reasoning: str | None = None,
    ) -> object:
        """Add a message to a session.

        Args:
            session_id: Session UUID.
            role: Message role (user/assistant/tool).
            content: Message content.
            reasoning: Optional agent reasoning.

        Returns:
            Created Message if session exists.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.add_message(
                session_id=session_id,
                role=role,
                content=content,
                reasoning=reasoning,
            )
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to add message: {exc}") from exc

    def get_messages(self, session_id: uuid.UUID, limit: int | None = None) -> list:
        """Get messages for a session.

        Args:
            session_id: Session UUID.
            limit: Optional limit.

        Returns:
            List of Message instances.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.get_messages(session_id, limit=limit)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to get messages: {exc}") from exc

    def get_recent_turns(self, session_id: uuid.UUID, count: int = 3) -> list:
        """Get recent non-archived turns.

        Args:
            session_id: Session UUID.
            count: Number of recent turns.

        Returns:
            List of recent Message instances.

        Raises:
            StorageError: If the underlying store operation fails.
        """
        try:
            return self._store.get_recent_turns(session_id, count=count)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Failed to get recent turns: {exc}") from exc
