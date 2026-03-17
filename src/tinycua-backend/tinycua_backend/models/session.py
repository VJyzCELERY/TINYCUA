"""Session model for tracking sessions in the backend."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.models.tenant import Tenant
    from tinycua_backend.models.agent import Agent


class Session(Base, UUIDMixin, TimestampMixin):
    """Session model for tracking conversation sessions.

    Sessions track the conversation between a user and an agent.
    Messages are stored in the SDK's SessionStore (PostgreSQL).
    """

    __tablename__ = "sessions"

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="sessions",
    )
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="sessions",
    )
