"""Session service with lineage tracking support."""

import uuid
from typing import Any, Optional

from sqlalchemy import select

from tinycua_backend.storage.database import get_session_local
from tinycua_backend.storage.models import Message, Session


class SessionService:
    """Service for managing sessions with lineage support."""

    def create_session(
        self,
        tenant_id: uuid.UUID,
        user_id: str,
        name: Optional[str] = None,
        agent_id: Optional[str] = None,
        parent_session_id: Optional[uuid.UUID] = None,
    ) -> Session:
        """Create a new session with optional lineage.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            name: Session name
            agent_id: Agent ID
            parent_session_id: Parent session ID for lineage

        Returns:
            Created session
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            lineage_depth = 0
            if parent_session_id:
                parent = db.get(Session, parent_session_id)
                if parent:
                    lineage_depth = parent.lineage_depth + 1

            session = Session(
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                agent_id=agent_id,
                parent_session_id=parent_session_id,
                lineage_depth=lineage_depth,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()

    def get_session(self, session_id: uuid.UUID) -> Optional[Session]:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session if found, None otherwise
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            return db.get(Session, session_id)
        finally:
            db.close()

    def get_lineage(self, session_id: uuid.UUID) -> list[Session]:
        """Get the parent chain of a session.

        Args:
            session_id: Session ID

        Returns:
            List of sessions from root to current
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            lineage: list[Session] = []
            current = db.get(Session, session_id)
            while current:
                lineage.insert(0, current)
                if current.parent_session_id:
                    current = db.get(Session, current.parent_session_id)
                else:
                    break
            return lineage
        finally:
            db.close()

    def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Add a message to a session.

        Args:
            session_id: Session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata

        Returns:
            Created message
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            max_turn = db.execute(
                select(Message.turn_index)
                .where(Message.session_id == session_id)
                .order_by(Message.turn_index.desc())
            ).scalar()

            turn_index = (max_turn or -1) + 1

            message = Message(
                session_id=session_id,
                turn_index=turn_index,
                role=role,
                content=content,
                message_metadata=metadata or {},
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            return message
        finally:
            db.close()

    def get_messages(
        self,
        session_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages
            offset: Number of messages to skip

        Returns:
            List of messages
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            query = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.turn_index)
            )
            if limit:
                query = query.limit(limit).offset(offset)
            return list(db.execute(query).scalars().all())
        finally:
            db.close()

    def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session and its messages.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        try:
            session = db.get(Session, session_id)
            if not session:
                return False
            db.delete(session)
            db.commit()
            return True
        finally:
            db.close()
