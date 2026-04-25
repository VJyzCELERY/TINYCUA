"""Authentication routes for registration and login."""

import threading
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth.core import (
    create_jwt_token,
    CurrentTenant,
    get_current_tenant,
    verify_password,
)
from tinycua_backend.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from tinycua_backend.auth.service import AuthService
from tinycua_backend.storage.database import get_db
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
    auth_service = AuthService(db)
    try:
        return auth_service.register(
            email=request.email,
            password=request.password,
            tenant_name=request.tenant_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
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
    if request.tenant_id:
        auth_service = AuthService(db)
        try:
            return auth_service.login(
                email=request.email,
                password=request.password,
                tenant_id=request.tenant_id,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )

    users = db.query(User).filter(User.email == request.email).all()

    if not users:
        verify_password(request.password, DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple tenants found for this email. Please specify tenant_id.",
        )

    user = users[0]

    if not user.password_hash or not verify_password(
        request.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_jwt_token(str(user.id), str(user.tenant_id), user.email)

    return TokenResponse(
        access_token=token,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
    )


class CurrentUserResponse(BaseModel):
    """Response model for current user."""

    user_id: str
    tenant_id: str
    email: str


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user(
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    """Get current authenticated user.

    Args:
        current_tenant: Current tenant from authentication
        db: Database session

    Returns:
        Current user information
    """
    from tinycua_backend.auth.models import User

    user = (
        db.query(User)
        .filter(
            User.id == current_tenant.user_id,
            User.tenant_id == current_tenant.tenant.id,
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return CurrentUserResponse(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
    )
