"""Database models for unified storage with SQLite and PostgreSQL support."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


def get_embedding_column():
    """Get the appropriate embedding column based on database type.

    For PostgreSQL with pgvector, returns a vector column.
    For SQLite or PostgreSQL without pgvector, returns JSON column.

    Returns:
        SQLAlchemy column definition for embeddings
    """
    try:
        from pgvector.sqlalchemy import Vector

        return mapped_column(Vector(1536), nullable=True)  # OpenAI ada-002 dimension
    except ImportError:
        return mapped_column(JSON, nullable=True)


class Session(Base):
    """Session model for storing conversation sessions.

    Uses 'sdk_sessions' table name to avoid conflicts with backend's sessions table.
    """

    __tablename__ = "sdk_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    has_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    summary_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_context_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sdk_sessions.id"), nullable=True
    )
    lineage_depth: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )
    parent_session: Mapped[Optional["Session"]] = relationship(
        "Session",
        remote_side="Session.id",
        back_populates="child_sessions",
        foreign_keys=[parent_session_id],
    )
    child_sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="parent_session",
        foreign_keys=[parent_session_id],
    )


class Message(Base):
    """Message model for storing conversation messages."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sdk_sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[Optional[list[float]]] = get_embedding_column()
    importance: Mapped[int] = mapped_column(Integer, default=5)
    memory_type: Mapped[str] = mapped_column(String(50), default="working")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship("Session", back_populates="messages")
