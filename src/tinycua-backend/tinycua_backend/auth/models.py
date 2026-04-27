"""User model for authentication."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.storage.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.tenant.models import Tenant


class User(Base, UUIDMixin, TimestampMixin):
    """User model for authentication.

    A user belongs to a tenant and can authenticate via JWT tokens.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )


class APIKey(Base, UUIDMixin):
    """API Key model for programmatic access.

    API keys are scoped to a tenant and can have specific permissions.
    """

    __tablename__ = "api_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    key_prefix: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    scopes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")
