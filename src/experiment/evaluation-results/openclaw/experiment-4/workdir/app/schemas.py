"""
Pydantic Schemas for Notion-like Web Application.
Defines request/response models for API endpoints. """
from datetime import datetime
from typing import List, Optional, Any, Literal
import uuid

from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from sqlalchemy.orm import Session
from app.database import get_db


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""
    sub: Optional[str] = None  # User ID from JWT
    exp: Optional[int] = None   # Expiration timestamp


class UserCreate(BaseModel):
    """User creation schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=User)


class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    """User response schema."""
    id: uuid.UUID
    email: str
    username: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class WorkspaceCreate(BaseModel):
    """Workspace creation schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    color: Optional[str] = "#007AFF"


class WorkspaceUpdate(BaseModel):
    """Workspace update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    color: Optional[str] = "#007AFF"
    is_archived: Optional[bool] = None


class WorkspaceResponse(BaseModel):
    """Workspace response schema."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    icon_url: Optional[str]
    cover_image_url: Optional[str]
    color: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    owner_id: Optional[uuid.UUID]
    
    class Config:
        from_attributes = True


class WorkspaceMemberCreate(BaseModel):
    """Workspace member creation schema."""
    user_id: uuid.UUID
    role: Literal['owner', 'editor', 'viewer'] = Field(..., pattern="^(owner|editor|viewer)$")


class PageCreate(BaseModel):
    """Page creation schema."""
    title: str = Field(..., min_length=1, max_length=500)
    icon_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    parent_page_id: Optional[uuid.UUID] = None  # For nested pages
    is_favorite: bool = False


class PageUpdate(BaseModel):
    """Page update schema."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    icon_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_favorite: Optional[bool] = None


class PageResponse(BaseModel):
    """Page response schema."""
    id: uuid.UUID
    title: str
    icon_url: Optional[str]
    cover_image_url: Optional[str]
    parent_page_id: Optional[uuid.UUID]
    position_index: int
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    owner_id: Optional[uuid.UUID]
    last_edited_by_id: Optional[uuid.UUID]
    
    class Config:
        from_attributes = True


class PageWithBlocksResponse(PageResponse):
    """Page response including blocks."""
    blocks: List['Block']  # Forward reference needed for circular dependency


class BlockCreate(BaseModel):
    """Block creation schema with block type enum."""
    block_type: Literal[
        'text', 'h1', 'h2', 'h3', 
        'bulleted_list_item', 'numbered_list_item', 
        'todo', 'quote', 'code_block', 'image', 'callout'
    ]
    text_content: Optional[str] = Field(None, max_length=500)
    language: Optional[str] = None  # For code blocks
    is_collapsed: bool = False
    list_style: Optional[Literal['bullet', 'number']] = None
    todo_checked: bool = False


class BlockUpdate(BaseModel):
    """Block update schema."""
    text_content: Optional[str] = Field(None, max_length=500)
    language: Optional[str] = None
    is_collapsed: Optional[bool] = None
    list_style: Optional[Literal['bullet', 'number']] = None
    todo_checked: Optional[bool] = None


class BlockResponse(BaseModel):
    """Block response schema."""
    id: uuid.UUID
    block_type: str
    text_content: Optional[str]
    language: Optional[str]
    is_collapsed: bool
    list_style: Optional[Literal['bullet', 'number']]
    todo_checked: bool
    created_at: datetime
    updated_at: datetime
    position_index: int
    
    class Config:
        from_attributes = True


class AttachmentCreate(BaseModel):
    """Attachment creation schema."""
    filename: str
    original_filename: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    storage_path: str
    thumbnail_url: Optional[str] = None


class AttachmentResponse(BaseModel):
    """Attachment response schema."""
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    storage_path: str
    thumbnail_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    """Comment creation schema."""
    target_type: Literal['page', 'block', 'attachment']
    target_id: uuid.UUID
    content: str = Field(..., min_length=1)


class ReactionCreate(BaseModel):
    """Reaction (emoji) creation schema."""
    emoji: str  # e.g., '👍', '❤️'
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "emoji": "👍",
                "target_type": "block",
                "target_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


class DatabaseRowCreate(BaseModel):
    """Database row creation schema."""
    title: str = Field(..., min_length=1, max_length=500)
    icon_url: Optional[str] = None
    cover_image_url: Optional[str] = None


class DatabaseRowResponse(BaseModel):
    """Database row response schema."""
    id: uuid.UUID
    title: str
    icon_url: Optional[str]
    cover_image_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class VersionResponse(BaseModel):
    """Page version history response."""
    id: uuid.UUID
    page_id: uuid.UUID
    version_number: int
    metadata_snapshot: dict  # JSON string parsed as dict
    created_at: datetime
    is_draft: bool
    
    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Search results response."""
    object: Literal['search-result'] = 'search-result'
    result_type: str  # 'page' or 'workspace'
    id: uuid.UUID
    created_at: datetime
    parent_id: Optional[uuid.UUID] = None
    title: str
    icon_url: Optional[str]
    cover_image_url: Optional[str]
    url: str
