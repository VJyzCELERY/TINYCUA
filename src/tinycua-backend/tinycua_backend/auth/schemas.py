"""Pydantic schemas for authentication requests and responses."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    tenant_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    tenant_id: str | None = None


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""

    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    api_key: str | None = None


class UserResponse(BaseModel):
    """Response model for user information."""

    user_id: str
    tenant_id: str
    email: str
