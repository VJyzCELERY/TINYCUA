"""Agent model for storing agent configurations."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.models.tenant import Tenant
    from tinycua_backend.models.session import Session


class Agent(Base, UUIDMixin, TimestampMixin):
    """Agent model for storing agent configurations.

    Agents are deployed configurations that can be executed by the runner.
    """

    __tablename__ = "agents"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="agents",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
