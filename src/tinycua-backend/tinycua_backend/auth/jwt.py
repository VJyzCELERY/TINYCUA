"""JWT token utilities for tinycua-backend."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt

from tinycua_backend.config import get_config

logger = logging.getLogger(__name__)


def _get_jwt_secret() -> str:
    """Get the JWT secret from config or environment.

    Returns:
        The JWT secret string

    Raises:
        RuntimeError: If no JWT secret is configured
    """
    config = get_config()
    secret = config.auth.jwt_secret or os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "JWT secret not configured. Set JWT_SECRET environment variable "
            "or auth.jwt_secret in config."
        )
    return secret


def create_jwt_token(
    user_id: str,
    tenant_id: str,
    email: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT token.

    Args:
        user_id: The user's ID
        tenant_id: The tenant's ID
        email: Optional user email
        expires_delta: Optional expiration time

    Returns:
        JWT token string
    """
    config = get_config()
    jwt_secret = _get_jwt_secret()
    if expires_delta is None:
        expires_delta = timedelta(hours=config.auth.jwt_expiration_hours)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    if email:
        payload["email"] = email
    return str(
        jwt.encode(
            payload,
            jwt_secret,
            algorithm=config.auth.jwt_algorithm,
        )
    )


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        The payload dict

    Raises:
        HTTPException: If the token is invalid
    """
    config = get_config()
    jwt_secret = _get_jwt_secret()
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=[config.auth.jwt_algorithm],
        )
        return dict(payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token",
        ) from e
