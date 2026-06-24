"""Pydantic schemas for blocks API endpoints."""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlmodel import SQLModel, Field


class BlockCreate(SQLModel):
    """Schema for creating a new block."""
    id: Optional[str] = Field(default=None)  # Allow optional client-provided ID
    type: str = Field(default="text")  # text, code, heading, image, bullet-list
    content: Optional[str] = None  # For text blocks
    parent_id: Optional[str] = None


class BlockUpdate(SQLModel):
    """Schema for updating an existing block."""
    type: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)  # For heading blocks


class BlockResponse(SQLModel):
    """Schema for block response including full details."""
    id: str
    parent_id: Optional[str] = None
    type: str
    content: Optional[str] = None
    
    class Config:
        from_attributes = True


__all__ = ["BlockCreate", "BlockUpdate", "BlockResponse"]
