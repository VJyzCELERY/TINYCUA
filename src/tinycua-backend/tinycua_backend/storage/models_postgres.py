"""PostgreSQL-specific models with UUID and tsvector support."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.storage.base import Base, TimestampMixin, UUIDMixin


class AgentPostgres(Base, UUIDMixin, TimestampMixin):
    """Agent model for PostgreSQL with UUID support."""

    __tablename__ = "agents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )


class ToolPostgres(Base, UUIDMixin, TimestampMixin):
    """Tool model for PostgreSQL with UUID support."""

    __tablename__ = "tools"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(1000),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        String(50000),
        nullable=False,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    external_dependencies: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
    )
    tool_dependencies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
    )
    version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )


class SessionPostgres(Base, UUIDMixin, TimestampMixin):
    """Session model for PostgreSQL with UUID support."""

    __tablename__ = "sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    agent_id: Mapped[str] = mapped_column(
        String(64),
        nullable=True,
    )
    agent_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    summary_md: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    full_context_md: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    has_summary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    parent_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.id"),
        nullable=True,
    )
    lineage_depth: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    parent_session: Mapped[Optional["SessionPostgres"]] = relationship(
        "SessionPostgres",
        remote_side="SessionPostgres.id",
        backref="child_sessions",
        foreign_keys=[parent_session_id],
    )

    __table_args__ = (
        Index("ix_sessions_tenant_user", "tenant_id", "user_id"),
        Index("ix_sessions_parent_session", "parent_session_id"),
    )


class MessagePostgres(Base, UUIDMixin, TimestampMixin):
    """Message model for PostgreSQL with tsvector for full-text search."""

    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.id"),
        nullable=False,
    )
    turn_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content_vector: Mapped[Optional[TSVECTOR]] = mapped_column(
        TSVECTOR,
        nullable=True,
    )
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )

    session: Mapped["SessionPostgres"] = relationship(
        "SessionPostgres",
        backref="messages",
    )

    __table_args__ = (
        Index("idx_messages_session_turn", "session_id", "turn_index"),
        Index("idx_messages_content_fts", "content_vector", postgresql_using="gin"),
    )
