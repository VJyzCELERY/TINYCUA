"""Shared API dependencies for tinycua-backend."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, HTTPException, status

from tinycua_backend.auth.core import get_current_tenant
from tinycua_backend.auth.dependencies import CurrentTenant
from tinycua_backend.storage.database import get_session_store


def get_store() -> Any:
    """Get cached SessionStore instance.

    Delegates to get_session_store in storage.database.
    """
    return get_session_store()


async def get_session_or_404(
    session_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
) -> Any:
    """Validate UUID, look up session, verify tenant, and return session.

    Args:
        session_id: The session ID string
        current: The current authenticated tenant

    Returns:
        The session object

    Raises:
        HTTPException: If session ID is invalid, not found, or access denied
    """
    try:
        uuid_session_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID",
        )

    store = get_store()
    session = store.get_session(uuid_session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    _verify_session_tenant(session, current)
    return session


def _verify_session_tenant(session: Any, current: CurrentTenant) -> None:
    """Verify that a session belongs to the current tenant.

    Args:
        session: The session from SessionStore
        current: The current authenticated tenant

    Raises:
        HTTPException: If session does not belong to the tenant
    """
    if current.is_system:
        return
    session_user_id = str(session.user_id) if session.user_id else None
    expected_id = str(current.user_id) if current.user_id else str(current.tenant.id)
    if session_user_id != expected_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to this tenant",
        )
