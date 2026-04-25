"""Authentication routes for registration and login."""

import threading
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tinycua_backend.auth.core import (
    create_api_key,
    create_jwt_token,
    get_tenant_filter,
    hash_api_key,
    hash_password,
    verify_password,
)
from tinycua_backend.storage.database import get_db
from tinycua_backend.tenant.models import Tenant
from tinycua_backend.auth.models import User

router = APIRouter(prefix="/v1/auth", tags=["auth"])

# In-memory rate limit storage: client_ip -> list of timestamps
_rate_limit_store: defaultdict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()

# Dummy bcrypt hash for timing-equalized login when user is not found.
# Using a real hash ensures the same code path as a valid password check.
DUMMY_HASH = "$2b$12$cDDFuYGuSw2dot4asdD61u2NNn9EZW1Tom/yGpOcSdFYJ2A0wDhPS"


def _rate_limit_dependency(
    max_requests: int = 5,
    window_seconds: int = 60,
) -> Any:
    """Create a rate limiting dependency.

    Args:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: Time window in seconds.

    Returns:
        A dependency function that enforces rate limiting.
    """

    def dependency(request: Request) -> None:
        """Enforce rate limit per client IP."""
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        with _rate_limit_lock:
            # Clean old entries outside the window
            _rate_limit_store[client_ip] = [
                t for t in _rate_limit_store[client_ip] if now - t < window_seconds
            ]

            if len(_rate_limit_store[client_ip]) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later.",
                )

            _rate_limit_store[client_ip].append(now)

    return dependency


class RegisterRequest(BaseModel):
    """Request model for registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    tenant_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for login."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    tenant_id: str


class TokenResponse(BaseModel):
    """Response model for auth tokens."""

    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    api_key: str | None = None


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_rate_limit_dependency(max_requests=5, window_seconds=60)),
) -> TokenResponse:
    """Register a new user and tenant.

    Args:
        request: Registration request
        db: Database session

    Returns:
        JWT token
    """
    # Create tenant first
    tenant = Tenant(name=request.tenant_name or f"Tenant for {request.email}")
    db.add(tenant)
    db.flush()

    # Check if user exists in this tenant (allows same email across tenants)
    query = db.query(User).filter(User.email == request.email)
    tenant_filter = get_tenant_filter(tenant, User)
    if tenant_filter is not None:
        query = query.filter(tenant_filter)
    existing_user = query.first()

    if existing_user:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    # Create user
    user = User(
        tenant_id=tenant.id,
        email=request.email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in this tenant",
        )

    # Create API key
    from tinycua_backend.auth.models import APIKey

    raw_key = create_api_key()
    api_key = APIKey(
        tenant_id=tenant.id,
        name="Default API Key",
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:8],
        scopes=[],
        is_active=True,
    )
    db.add(api_key)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in this tenant",
        )

    # Generate JWT token
    token = create_jwt_token(str(user.id), str(tenant.id))

    return TokenResponse(
        access_token=token,
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        api_key=raw_key,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_rate_limit_dependency(max_requests=5, window_seconds=60)),
) -> TokenResponse:
    """Login with email and password.

    Args:
        request: Login request
        db: Database session

    Returns:
        JWT token
    """
    import uuid

    try:
        tenant_uuid = uuid.UUID(request.tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    user = (
        db.query(User)
        .filter(User.email == request.email, User.tenant_id == tenant_uuid)
        .first()
    )
    if not user:
        # Timing-equalized failure: perform dummy bcrypt to match "wrong password" path
        verify_password(request.password, DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.password_hash or not verify_password(
        request.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_jwt_token(str(user.id), str(user.tenant_id))

    return TokenResponse(
        access_token=token,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
    )
