"""Tool model for storing custom agent tools."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tinycua_backend.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from tinycua_backend.models.tenant import Tenant


class Tool(Base, UUIDMixin, TimestampMixin):
    """Tool model for storing custom agent tools.

    Custom tools are stored in the backend and referenced by agents via tool_id.
    """

    __tablename__ = "tools"

    tenant_id: Mapped[str] = mapped_column(
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
    parameters: Mapped[dict] = mapped_column(
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
    tool_dependencies: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
    )
    version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="tools",
    )
