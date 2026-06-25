from datetime import datetime
from typing import Optional, List
from uuid import uuid4
import sqlalchemy as sa
from sqlmodel import SQLModel, Field


class Block(SQLModel, table=True):
    __tablename__ = "blocks"

    id: str | None = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    parent_id: str | None = Field(
        default=None, 
        index=True  # For nested block structure (null for root blocks)
    )
    type: str = Field(
        default="text"
    )
    text_content: Optional[str] = Field(default=None)  # Content for text blocks only

    __table_args__ = (
        sa.CheckConstraint("type IN ('text', 'code', 'heading', 'image', 'bullet-list')", name="chk_block_type"),
    )


class Page(SQLModel, table=True):
    __tablename__ = "pages"

    id: str | None = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str = Field(min_length=1)  # Required page title
    
    # Recursive parent-child pages structure (like folders/nested pages in Notion)
    parent_page_id: str | None = Field(
        default=None, 
        index=True  # Nullable for root-level pages
    )


class PageBlock(SQLModel, table=True):
    """Association table for many-to-many relation between Pages and Blocks."""
    __tablename__ = "page_blocks"

    page_id: str = Field(foreign_key="pages.id", primary_key=True)
    block_id: str = Field(foreign_key="blocks.id", primary_key=True)


__all__ = ["Block", "Page", "PageBlock"]

# =============================================================================
# Metadata Tables: user_blocks, page_views, document_properties
# =============================================================================


class UserBlock(SQLModel, table=True):
    """Tracks block ownership/collaboration - which users have access to blocks."""
    __tablename__ = "user_blocks"

    id: str | None = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True)  # User ID (from auth system or direct string)
    block_id: str = Field(foreign_key="blocks.id", index=True)
    
    # Permission level for this user on the block
    permission_level: str = Field(default="read")

    created_at: datetime | None = Field(default_factory=lambda: datetime.utcnow(), index=True)
    updated_at: datetime | None = Field(default=None, index=True)


class PageView(SQLModel, table=True):
    """Tracks page views for analytics."""
    __tablename__ = "page_views"

    id: str | None = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    page_id: str = Field(foreign_key="pages.id", index=True)
    user_id: str = Field(index=True)  # Who viewed the page
    view_timestamp: datetime = Field(sa_column=sa.Column(sa.DateTime, default=datetime.utcnow))
    
    # Optional metadata about the view session
    referrer_url: Optional[str] = Field(default=None)
    device_type: Optional[str] = Field(default=None)  # desktop/mobile/tablet

    __table_args__ = (
        sa.Index("ix_page_view_user_time", "page_id", "user_id"),
    )


class DocumentProperties(SQLModel, table=True):
    """Stores metadata and properties for pages/documents."""
    __tablename__ = "document_properties"

    id: str | None = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    page_id: str = Field(foreign_key="pages.id", unique=True, index=True)  # One row per page
    
    # Title and basic info (can differ from Page.title if customized)
    title: Optional[str] = Field(default=None)
    
    # Visual properties
    icon_url: Optional[str] = Field(default=None)
    cover_image_url: Optional[str] = Field(default=None)
    
    # Status flags
    is_favorite: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, default=False))
    is_archived: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, default=False))
    
    # Metadata from users
    created_by_user_id: str = Field(index=True)
    last_edited_by_user_id: Optional[str] = Field(default=None, index=True)
    
    # Timestamps
    created_at: datetime | None = Field(default_factory=lambda: datetime.utcnow(), index=True)
    updated_at: datetime | None = Field(default=None, index=True)


__all__ = ["Block", "Page", "PageBlock", "UserBlock", "PageView", "DocumentProperties"]


# Base class for Alembic autogenerate support
class Base(SQLModel):
    pass

Base.metadata.tables["blocks"].create_if_not_exists = True
Base.metadata.tables["pages"].create_if_not_exists = True
Base.metadata.tables["page_blocks"].create_if_not_exists = True
Base.metadata.tables["user_blocks"].create_if_not_exists = True
Base.metadata.tables["page_views"].create_if_not_exists = True
Base.metadata.tables["document_properties"].create_if_not_exists = True