"""Extracted SessionStore class and factory function."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SQLSession, sessionmaker

from tinycua_sdk.storage.models import Base, Message, Session


class SessionStore:
    """Unified storage for sessions and messages.

    Supports SQLite (local) and PostgreSQL (production) via DATABASE_URL.

    Features:
    - SQLite: Uses JSON for embeddings, Python for similarity calc
    - PostgreSQL: Uses pgvector if available, falls back to JSON + Python

    Usage:
        # SQLite (local)
        store = SessionStore("sqlite:///./tinycua.db")

        # PostgreSQL (production)
        store = SessionStore("postgresql://user:pass@localhost:5432/tinycua")
    """

    def __init__(self, database_url: str):
        """Initialize the session store.

        Args:
            database_url: Database URL (e.g., sqlite:///./tinycua.db)
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.session_factory = sessionmaker(bind=self.engine)
        self._db_type = self._detect_db_type()

    def _detect_db_type(self) -> str:
        """Detect database type from URL.

        Returns:
            'postgresql' or 'sqlite'
        """
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        return "sqlite"

    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL."""
        return self._db_type == "postgresql"

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return self._db_type == "sqlite"

    def has_pgvector(self) -> bool:
        """Check if pgvector is available.

        Returns:
            True if pgvector is available
        """
        if not self.is_postgresql:
            return False
        try:
            # Import pgvector to register vector type with SQLAlchemy
            # ruff: noqa: F401
            import pgvector.sqlalchemy  # type: ignore[import-not-found]

            return True
        except ImportError:
            return False

    def create_tables(self) -> None:
        """Create all tables in the database."""
        Base.metadata.create_all(self.engine)

    def get_db_session(self) -> SQLSession:
        """Get a new database session for custom queries.

        This is the public API for obtaining a raw SQLAlchemy session.
        Prefer store methods for standard CRUD operations.

        Returns:
            SQLSession instance
        """
        return self.session_factory()

    def _get_session(self) -> SQLSession:
        """Get a new database session (internal compatibility alias).

        Returns:
            SQLSession instance
        """
        return self.get_db_session()

    # Session operations

    def create_session(
        self,
        name: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        session_id: uuid.UUID | None = None,
        parent_session_id: uuid.UUID | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            name: Session name
            user_id: Optional user ID for multi-tenancy
            tenant_id: Optional tenant ID for multi-tenancy
            session_id: Optional specific session ID (for external session management)
            parent_session_id: Optional parent session ID for lineage

        Returns:
            Created Session instance
        """
        with self._get_session() as db:
            lineage_depth = 0
            if parent_session_id:
                parent = db.get(Session, parent_session_id)
                if parent:
                    lineage_depth = getattr(parent, "lineage_depth", 0) + 1
            if session_id:
                session = Session(
                    id=session_id,
                    name=name,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    parent_session_id=parent_session_id,
                    lineage_depth=lineage_depth,
                )
            else:
                session = Session(
                    name=name,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    parent_session_id=parent_session_id,
                    lineage_depth=lineage_depth,
                )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def get_session(self, session_id: uuid.UUID) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session if found, None otherwise
        """
        with self._get_session() as db:
            return db.get(Session, session_id)

    def get_session_by_name(self, name: str) -> Session | None:
        """Get a session by name.

        Args:
            name: Session name (exact match, case-sensitive)

        Returns:
            Session if found, None otherwise
        """
        with self._get_session() as db:
            stmt = select(Session).where(Session.name == name)
            return db.execute(stmt).scalars().first()

    def list_sessions(self, user_id: str | None = None) -> list[Session]:
        """List all sessions, optionally filtered by user_id.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of Session instances
        """
        with self._get_session() as db:
            stmt = select(Session)
            if user_id:
                stmt = stmt.where(Session.user_id == user_id)
            stmt = stmt.order_by(Session.updated_at.desc())
            return list(db.execute(stmt).scalars().all())

    def update_session(self, session_id: uuid.UUID, **kwargs: Any) -> Session | None:
        """Update a session.

        Args:
            session_id: Session UUID
            **kwargs: Fields to update

        Returns:
            Updated Session if found, None otherwise
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return None
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            db.commit()
            db.refresh(session)
            return session

    def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return False
            db.delete(session)
            db.commit()
            return True

    def get_lineage(self, session_id: uuid.UUID) -> list[Session]:
        """Get the parent chain of a session.

        Args:
            session_id: Session UUID

        Returns:
            List of sessions from root to current
        """
        with self._get_session() as db:
            lineage: list[Session] = []
            current = db.get(Session, session_id)
            while current:
                lineage.insert(0, current)
                if current.parent_session_id:
                    current = db.get(Session, current.parent_session_id)
                else:
                    break
            return lineage

    # Message operations

    def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        reasoning: str | None = None,
    ) -> Message | None:
        """Add a message to a session.

        Args:
            session_id: Session UUID
            role: Message role (user/assistant/tool)
            content: Message content
            reasoning: Optional agent reasoning

        Returns:
            Created Message if session exists, None otherwise
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return None

            stmt = select(Message).where(Message.session_id == session_id)
            existing_messages = db.execute(stmt).scalars().all()
            turn_index = len(existing_messages)

            message = Message(
                session_id=session_id,
                role=role,
                content=content,
                reasoning=reasoning,
                turn_index=turn_index,
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            return message

    def get_messages(
        self, session_id: uuid.UUID, limit: int | None = None
    ) -> list[Message]:
        """Get messages for a session.

        Args:
            session_id: Session UUID
            limit: Optional limit

        Returns:
            List of Message instances
        """
        with self._get_session() as db:
            stmt = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.turn_index.asc())
            )
            if limit:
                stmt = stmt.limit(limit)
            return list(db.execute(stmt).scalars().all())

    def get_messages_by_role(self, session_id: uuid.UUID, role: str) -> list[Message]:
        """Get messages for a session filtered by role.

        Args:
            session_id: Session UUID
            role: Message role (user/assistant/tool)

        Returns:
            List of Message instances with matching role, ordered by turn_index ascending
        """
        with self._get_session() as db:
            stmt = (
                select(Message)
                .where(Message.session_id == session_id)
                .where(Message.role == role)
                .order_by(Message.turn_index.asc())
            )
            return list(db.execute(stmt).scalars().all())

    def archive_message(self, message_id: uuid.UUID) -> Message | None:
        """Archive a message.

        Args:
            message_id: Message UUID

        Returns:
            Archived Message if found, None otherwise
        """
        with self._get_session() as db:
            message = db.get(Message, message_id)
            if not message:
                return None
            message.is_archived = True
            db.commit()
            db.refresh(message)
            return message

    def delete_message(self, message_id: uuid.UUID) -> bool:
        """Delete a message permanently.

        Args:
            message_id: Message UUID

        Returns:
            True if deleted, False if not found
        """
        with self._get_session() as db:
            message = db.get(Message, message_id)
            if not message:
                return False
            db.delete(message)
            db.commit()
            return True

    # Context retrieval

    def get_recent_turns(self, session_id: uuid.UUID, count: int = 3) -> list[Message]:
        """Get recent non-archived turns.

        Args:
            session_id: Session UUID
            count: Number of recent turns

        Returns:
            List of recent Message instances
        """
        with self._get_session() as db:
            stmt = (
                select(Message)
                .where(Message.session_id == session_id)
                .where(Message.is_archived == False)  # noqa: E712
                .order_by(Message.turn_index.desc())
                .limit(count)
            )
            results = db.execute(stmt).scalars().all()
            return list(reversed(results))

    def update_full_context(self, session_id: uuid.UUID) -> str:
        """Update full_context_md for a session.

        Args:
            session_id: Session UUID

        Returns:
            The updated full_context_md
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return ""

            messages = (
                db.execute(
                    select(Message)
                    .where(Message.session_id == session_id)
                    .order_by(Message.turn_index.asc())
                )
                .scalars()
                .all()
            )

            md_lines = [
                f"# Session: {session.name}",
                f"Created: {session.created_at.isoformat()}",
                "",
                "---",
                "",
            ]

            for msg in messages:
                role_label = msg.role.capitalize()
                md_lines.append(f"## Turn {msg.turn_index}")
                md_lines.append(f"**{role_label}**: {msg.content}")
                md_lines.append("")

            full_context = "\n".join(md_lines)
            session.full_context_md = full_context
            db.commit()
            return full_context

    def search_grep(
        self, session_id: uuid.UUID, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search full context using text matching.

        Args:
            session_id: Session UUID
            query: Search query
            limit: Max results

        Returns:
            List of matching message dicts
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session or not session.full_context_md:
                return []

            full_context = session.full_context_md
            lines = full_context.split("\n")
            matching_lines = []
            current_turn = []

            for line in lines:
                if query.lower() in line.lower():
                    current_turn.append(line)
                elif line.startswith("## Turn "):
                    if current_turn:
                        matching_lines.extend(current_turn)
                        matching_lines.append("")
                    current_turn = [line]
                elif line.strip():
                    current_turn.append(line)

            if current_turn:
                matching_lines.extend(current_turn)

            result_text = "\n".join(matching_lines[: limit * 50])

            return [{"content": result_text, "matches": len(matching_lines)}]

    def update_summary(self, session_id: uuid.UUID, summary_md: str) -> Session | None:
        """Update session summary.

        Args:
            session_id: Session UUID
            summary_md: Summary markdown

        Returns:
            Updated Session if found, None otherwise
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return None
            session.summary_md = summary_md
            session.has_summary = True
            session.summary_updated_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
            return session

    def get_summary(self, session_id: uuid.UUID) -> str | None:
        """Get session summary.

        Args:
            session_id: Session UUID

        Returns:
            Summary markdown if exists, None otherwise
        """
        with self._get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return None
            return session.summary_md


# Default store singleton for factory function
_default_store: SessionStore | None = None


def get_session_store(database_url: str | None = None) -> SessionStore:
    """Get or create the default session store.

    Fallback chain for database_url:
    1. If database_url parameter is provided -> use it (creates new instance)
    2. Else try lazy import of SDKConfig -> use SDKConfig().memory.database_url
    3. Else -> use "sqlite:///./tinycua.db"

    On first creation of the default store, create_tables() is called
    to ensure the database schema exists.

    Args:
        database_url: Optional database URL. If provided, creates and
            returns a new SessionStore instance (not cached).

    Returns:
        Configured SessionStore instance.
    """
    global _default_store

    if database_url is not None:
        # Custom URL: create new instance, not cached
        store = SessionStore(database_url)
        store.create_tables()
        return store

    if _default_store is not None:
        return _default_store

    # Determine database URL via lazy import of SDKConfig
    resolved_url = "sqlite:///./tinycua.db"
    try:
        from tinycua_sdk.core.config import SDKConfig

        resolved_url = SDKConfig().memory.database_url
    except (OSError, ValueError, ImportError, TypeError):
        pass  # Fall back to default

    _default_store = SessionStore(resolved_url)
    _default_store.create_tables()
    return _default_store
