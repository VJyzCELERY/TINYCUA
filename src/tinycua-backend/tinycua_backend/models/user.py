"""User model for authentication."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.models.tenant import Tenant


class User(Base, UUIDMixin, TimestampMixin):
    """User model for authentication.

    A user belongs to a tenant and can authenticate via JWT tokens.
    """

    __tablename__ = "users"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="users",
    )
