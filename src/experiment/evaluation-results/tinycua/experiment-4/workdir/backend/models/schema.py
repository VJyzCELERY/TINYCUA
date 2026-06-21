"""
SQLite Database Schema for Notion-like Application
Models: Users, Documents, Pages, Blocks, and Metadata
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    """User accounts for authentication and ownership."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="owner")


class Document(Base):
    """Documents (workspaces/projects) - top-level containers."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    icon_url = Column(String(500))
    cover_image_url = Column(String(1000))
    
    # Permissions and sharing
    is_private = Column(Boolean, default=True)  # Only owner can access
    is_shared = Column(Boolean, default=False)   # Can be shared with users
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", foreign_keys=[created_by], back_populates="documents")
    root_pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    """Pages within documents - can have nested children."""
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    
    # Content properties
    title = Column(String(255), nullable=False)
    icon_url = Column(String(500))
    cover_image_url = Column(String(1000))
    is_favorite = Column(Boolean, default=False)
    
    # Positioning for drag-and-drop ordering
    position_index = Column(Integer, default=0)
    
    # Relationships - parent and document
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # NULL for root pages
    parent_page_id = Column(Integer, ForeignKey("pages.id"))  # For nested pages
    
    document = relationship("Document", back_populates="root_pages")
    parent_page = relationship("Page", remote_side=[id], backref="children")
    
    # Relationships - blocks (content)
    blocks = relationship("Block", back_populates="page")


class Block(Base):
    """Content blocks within pages (paragraphs, headings, code blocks, etc.)."""
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Content data - stored as JSON for flexible content types
    block_type = Column(String(50), nullable=False)  # e.g., 'paragraph', 'heading_1', 'heading_2', 'bulleted_list_item'
    text_content = Column(Text)  # Rich text or plain text content
    
    # Properties for different block types (stored as JSON)
    properties = Column(Text)  # e.g., {'color': 'default', 'bold': True} for heading blocks
    
    # Positioning within page
    position_index = Column(Integer, default=0)
    
    # Relationships
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    
    page = relationship("Page", back_populates="blocks")


class BlockComment(Base):
    """Comments on blocks for collaboration."""
    __tablename__ = "block_comments"

    id = Column(Integer, primary_key=True, index=True)
    
    # Comment content
    content = Column(Text, nullable=False)
    
    # Author and relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    block_id = Column(Integer, ForeignKey("blocks.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    block = relationship("Block", back_populates="comments")


class PageComment(Base):
    """Comments on pages for collaboration."""
    __tablename__ = "page_comments"

    id = Column(Integer, primary_key=True, index=True)
    
    # Comment content
    content = Column(Text, nullable=False)
    
    # Author and relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    page = relationship("Page", back_populates="comments")


class PageFavorite(Base):
    """Favorites for pages."""
    __tablename__ = "page_favorites"

    id = Column(Integer, primary_key=True)
    
    # Relationships - composite unique constraint on user_id + page_id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentShare(Base):
    """Shared documents with users."""
    __tablename__ = "document_shares"

    id = Column(Integer, primary_key=True)
    
    # Relationships
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Permission level: 'view', 'comment', 'edit'
    permission_level = Column(String(20), default='view')
    
    created_at = Column(DateTime, default=datetime.utcnow)


class SearchIndex(Base):
    """Search index for full-text search."""
    __tablename__ = "search_index"

    id = Column(Integer, primary_key=True)
    
    # Indexed content
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id"))
    
    searchable_text = Column(Text, nullable=False)  # Full text to search
    search_metadata = Column(Text)  # JSON metadata for filtering
    
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    """Audit log of all activities."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"))
    page_id = Column(Integer, ForeignKey("pages.id"))
    block_id = Column(Integer, ForeignKey("blocks.id"))
    
    action_type = Column(String(50), nullable=False)  # 'create', 'update', 'delete', 'share'
    old_value = Column(Text)  # JSON snapshot of previous state (for audit)
    new_value = Column(Text)  # JSON snapshot of current state
    
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseTable(Base):
    """Notion-style databases with custom properties."""
    __tablename__ = "database_tables"

    id = Column(Integer, primary_key=True)
    
    # Basic info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    icon_url = Column(String(500))
    cover_image_url = Column(String(1000))
    
    # Relationships
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    parent_page_id = Column(Integer, ForeignKey("pages.id"))
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="root_pages")
    parent_page = relationship("Page", remote_side=[id], backref="databases")
    owner = relationship("User", foreign_keys=[created_by])


class DatabaseProperty(Base):
    """Properties for database rows (text, select, date, etc.)."""
    __tablename__ = "database_properties"

    id = Column(Integer, primary_key=True)
    
    # Property configuration
    name = Column(String(100), nullable=False)  # e.g., 'Status', 'Priority'
    property_type = Column(String(50), nullable=False)  # 'text', 'select', 'multi_select', 'date', 'number', 'formula'
    
    # Property-specific settings (stored as JSON for flexibility)
    options = Column(Text)  # e.g., {'options': ['Done', 'In Progress', 'Backlog']} for select type
    formula_expression = Column(String(200))  # For formula property types
    
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseRow(Base):
    """Rows within databases."""
    __tablename__ = "database_rows"

    id = Column(Integer, primary_key=True)
    
    database_id = Column(Integer, ForeignKey("database_tables.id"), nullable=False)
    
    # Row content - stored as JSON for flexibility with different property types
    properties_data = Column(Text, nullable=False)  # e.g., {'Status': 'Done', 'Priority': 3}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


"""
Schema Summary:

1. Users - Authentication and user accounts
2. Documents - Top-level containers (workspaces/projects)
3. Pages - Content pages within documents (can be nested)
4. Blocks - Rich text content blocks within pages (paragraphs, headings, lists, etc.)
5. BlockComments/PageComments - Collaboration comments

Additional tables:
- PageFavorites - User favorites for quick access
- DocumentShares - Shared document permissions with users
- SearchIndex - Full-text search index
- ActivityLog - Audit trail of all actions
- DatabaseTable + DatabaseProperty + DatabaseRow - Notion-style databases with custom properties
"""
