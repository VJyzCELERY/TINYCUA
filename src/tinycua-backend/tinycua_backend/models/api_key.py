"""API Key model for programmatic access."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.models.tenant import Tenant


class APIKey(Base, UUIDMixin):
    """API Key model for programmatic access.

    API keys are scoped to a tenant and can have specific permissions.
    """

    __tablename__ = "api_keys"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="api_keys",
    )
