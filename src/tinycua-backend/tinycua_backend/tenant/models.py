"""Tenant model for multi-tenancy."""

from enum import Enum

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.storage.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.auth.models import APIKey, User
    from tinycua_backend.storage.models import Agent, Tool


class TenantType(str, Enum):
    """Type of tenant.

    STANDARD - Normal tenant with regular access
    GUEST - Temporary guest tenant for unauthenticated access
    SYSTEM - System tenant for global API key (bypasses tenant restrictions)
    """

    STANDARD = "standard"
    GUEST = "guest"
    SYSTEM = "system"


class Tenant(Base, UUIDMixin, TimestampMixin):
    """Tenant model for multi-tenancy support.

    A tenant represents an organization or entity that owns resources.
    All resources (agents, sessions, users) belong to a tenant.

    Guest tenants are special - they don't persist sessions and are
    shared among multiple users for temporary usage.
    """

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_type: Mapped[TenantType] = mapped_column(
        String(20), nullable=False, default=TenantType.STANDARD
    )

    __table_args__ = (
        Index(
            "uq_system_guest_tenant_type",
            "tenant_type",
            unique=True,
            sqlite_where=text("tenant_type IN ('system', 'guest')"),
            postgresql_where=text("tenant_type IN ('system', 'guest')"),
        ),
    )

    users: Mapped[list["User"]] = relationship(
        "User",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        cascade="all, delete-orphan",
        back_populates="tenant",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        cascade="all, delete-orphan",
    )
    tools: Mapped[list["Tool"]] = relationship(
        "Tool",
        cascade="all, delete-orphan",
    )
