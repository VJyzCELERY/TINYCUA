"""Session API routes using SessionStore for persistence."""

import threading
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from tinycua_backend.auth.core import CurrentTenant, get_current_tenant
from tinycua_backend.config import get_config

# NOTE: SessionStore is imported from tinycua_sdk for storage-only purposes.
# The backend does not use any execution logic from the SDK (agent loops,
# tools, memory management, etc.). This import is strictly for persisting
# and retrieving session/message data via the SDK's storage layer.
from tinycua_sdk.storage.store import SessionStore

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

_store: SessionStore | None = None
_store_lock = threading.Lock()


def get_store() -> SessionStore:
    """Get cached SessionStore instance.

    The store is cached globally and recreated if the database URL changes.
    """
    global _store
    config = get_config()
    if _store is None or _store.database_url != config.database.url:
        with _store_lock:
            if _store is None or _store.database_url != config.database.url:
                _store = SessionStore(config.database.url)
    return _store


class SessionCreate(BaseModel):
    """Request model for creating a session."""

    agent_id: str
    name: str | None = None


class SessionUpdate(BaseModel):
    """Request model for updating a session."""

    name: str | None = None


class SessionResponse(BaseModel):
    """Response model for a session."""

    id: str
    name: str | None
    created_at: str
    updated_at: str


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


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    current: CurrentTenant = Depends(get_current_tenant),
) -> SessionResponse:
    """Create a new session.

    Args:
        session_data: The session data
        current: The current tenant

    Returns:
        The created session
    """
    store = get_store()
    user_id = str(current.user_id) if current.user_id else str(current.tenant.id)
    session = store.create_session(
        name=session_data.name or "Session",
        user_id=user_id,
    )

    return SessionResponse(
        id=str(session.id),
        name=session.name,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
    )


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current: CurrentTenant = Depends(get_current_tenant),
    limit: int = 100,
    offset: int = 0,
) -> list[SessionResponse]:
    """List all sessions for the current tenant.

    Args:
        current: The current tenant
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of sessions
    """
    store = get_store()
    if current.is_system:
        sessions = store.list_sessions()
    else:
        user_id = str(current.user_id) if current.user_id else str(current.tenant.id)
        sessions = store.list_sessions(user_id=user_id)

    return [
        SessionResponse(
            id=str(s.id),
            name=s.name,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions[offset : offset + limit]
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
) -> SessionResponse:
    """Get a session by ID.

    Args:
        session_id: The session ID
        current: The current tenant

    Returns:
        The session

    Raises:
        HTTPException: If session not found or access denied
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

    return SessionResponse(
        id=str(session.id),
        name=session.name,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
    )


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    session_data: SessionUpdate,
    current: CurrentTenant = Depends(get_current_tenant),
) -> SessionResponse:
    """Update a session.

    Args:
        session_id: The session ID
        session_data: The session data to update
        current: The current tenant

    Returns:
        The updated session

    Raises:
        HTTPException: If session not found or access denied
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

    kwargs = {}
    if session_data.name is not None:
        kwargs["name"] = session_data.name

    updated = store.update_session(uuid_session_id, **kwargs)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse(
        id=str(updated.id),
        name=updated.name,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
) -> None:
    """Delete a session.

    Args:
        session_id: The session ID
        current: The current tenant

    Raises:
        HTTPException: If session not found or access denied
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

    deleted = store.delete_session(uuid_session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
