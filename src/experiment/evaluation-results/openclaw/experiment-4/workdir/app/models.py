"""
SQLAlchemy ORM Models for Notion-like Web Application.
Defines Users, Workspaces, Pages/Blocks, Attachments, and Comments. """
from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum, CheckConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

Base = declarative_base()

# Block Type Enum for rich text editor support
class BlockType(str, Enum):
    """Supported block types in the Notion-like editor."""
    TEXT = "text"
    HEADING_1 = "h1"
    HEADING_2 = "h2"
    HEADING_3 = "h3"
    BULLETED_LIST = "bulleted_list_item"
    NUMBERED_LIST = "numbered_list_item"
    TODO = "todo"
    QUOTE = "quote"
    CODE_BLOCK = "code_block"
    IMAGE = "image"
    CALLOUT = "callout"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(String(255))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    workspaces = relationship("Workspace", back_populates="owner")
    pages = relationship("Page", back_populates="owner")
    comments = relationship("Comment", back_populates="author")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Workspace(Base):
    """Workspace model for organizing pages and content."""
    __tablename__ = "workspaces"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    icon_url = Column(String(500))
    cover_image_url = Column(String(1000))
    color = Column(String(7))  # Hex color code for workspace accent
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id], back_populates="workspaces")
    pages = relationship("Page", back_populates="workspace", cascade="all, delete-orphan")
    members = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name='{self.name}')>"


class WorkspaceMember(Base):
    """Model for workspace membership with permissions."""
    __tablename__ = "workspace_members"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    workspace_id = Column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id"))
    role = Column(String(50), nullable=False)  # 'owner', 'editor', 'viewer'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="check_workspace_role"
        ),
    )
    
    # Relationships
    user = relationship("User", back_populates=None)
    workspace = relationship("Workspace", back_populates="members")


class Page(Base):
    """Page model representing a Notion-like page with properties."""
    __tablename__ = "pages"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(PG_UUID(as_uuid=True), ForeignKey("workspaces.id"))
    title = Column(String(500), nullable=False)
    icon_url = Column(String(500))  # Page icon (emoji or image URL)
    cover_image_url = Column(String(1000))  # Cover image URL
    is_favorite = Column(Boolean, default=False)
    parent_page_id = Column(PG_UUID(as_uuid=True), ForeignKey("pages.id"))
    position_index = Column(Integer)  # For ordering pages with same parent
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )
    deleted_at = Column(DateTime(timezone=True))  # Soft delete
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    last_edited_by_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    workspace = relationship("Workspace", back_populates="pages")
    blocks = relationship("Block", back_populates="page