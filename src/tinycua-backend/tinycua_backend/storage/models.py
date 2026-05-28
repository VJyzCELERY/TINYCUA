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



