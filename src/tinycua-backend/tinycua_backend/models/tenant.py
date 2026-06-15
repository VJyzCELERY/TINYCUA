"""Tenant model for multi-tenancy."""

from enum import Enum

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.models.user import User
    from tinycua_backend.models.api_key import APIKey
    from tinycua_backend.models.agent import Agent
    from tinycua_backend.models.tool import Tool
    from tinycua_backend.models.session import Session


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

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    tools: Mapped[list["Tool"]] = relationship(
        "Tool",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
