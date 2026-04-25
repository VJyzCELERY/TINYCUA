"""Tenant middleware for request-scoped tenant isolation."""

from collections.abc import Callable
from typing import Awaitable

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from tinycua_backend.auth.core import decode_jwt_token

PUBLIC_PATHS = ["/health", "/v1/auth/register", "/v1/auth/login"]


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware for tenant isolation.

    Extracts tenant_id from JWT token and adds it to request state.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and extract tenant information.

        Args:
            request: The incoming request
            call_next: The next middleware/handler

        Returns:
            Response from the next handler

        Raises:
            HTTPException: If authentication fails
        """
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization",
            )

        token = auth_header.replace("Bearer ", "")

        try:
            payload = decode_jwt_token(token)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        request.state.tenant_id = payload.get("tenant_id")
        request.state.user_id = payload.get("sub")
        request.state.email = payload.get("email")

        return await call_next(request)


def get_current_tenant_id(request: Request) -> str:
    """Get current tenant ID from request.

    Args:
        request: The incoming request

    Returns:
        Tenant ID string

    Raises:
        HTTPException: If tenant_id not found in request state
    """
    tenant_id: str | None = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found in request",
        )
    return tenant_id


def get_current_user_id(request: Request) -> str:
    """Get current user ID from request.

    Args:
        request: The incoming request

    Returns:
        User ID string

    Raises:
        HTTPException: If user_id not found in request state
    """
    user_id: str | None = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in request",
        )
    return user_id
