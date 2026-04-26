"""Agent model for storing agent configurations."""

import uuid

from typing import Any, Optional

from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.storage.base import Base, TimestampMixin, UUIDMixin


class Agent(Base, UUIDMixin, TimestampMixin):
    """Agent model for storing agent configurations.

    Agents are deployed configurations that can be executed by the runner.
    """

    __tablename__ = "agents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
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


class Tool(Base, UUIDMixin, TimestampMixin):
    """Tool model for storing custom agent tools.

    Custom tools are stored in the backend and referenced by agents via tool_id.
    """

    __tablename__ = "tools"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
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


class Session(Base, UUIDMixin, TimestampMixin):
    """Session model for tracking conversation sessions with lineage.

    Sessions can have a parent_session_id to track lineage/threading.
    """

    __tablename__ = "sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
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

    parent_session: Mapped[Optional["Session"]] = relationship(
        "Session",
        remote_side="Session.id",
        backref="child_sessions",
        foreign_keys=[parent_session_id],
    )

    __table_args__ = (
        Index("ix_sessions_tenant_user", "tenant_id", "user_id"),
        Index("ix_sessions_parent_session", "parent_session_id"),
    )


class Message(Base, UUIDMixin, TimestampMixin):
    """Message model for storing conversation turns within sessions.

    Each message belongs to a session and has a turn_index to maintain order.
    """

    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
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
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )

    session: Mapped["Session"] = relationship(
        "Session",
        backref="messages",
    )

    __table_args__ = (Index("idx_messages_session_turn", "session_id", "turn_index"),)
