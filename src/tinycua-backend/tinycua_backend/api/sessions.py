"""Session API routes using SessionStore for persistence."""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from sqlalchemy import select
from tinycua_backend.api.dependencies import (
    _verify_session_tenant,
    get_session_or_404,
    get_store,
)
from tinycua_backend.auth.core import CurrentTenant, get_current_tenant
from tinycua_backend.storage.search_sqlite import SQLiteSearch
from tinycua_sdk.storage.models import Message, Session as SessionModel

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    """Request model for creating a session."""

    name: str | None = None
    parent_session_id: str | None = None


class SessionUpdate(BaseModel):
    """Request model for updating a session."""

    name: str | None = None


class SessionResponse(BaseModel):
    """Response model for a session."""

    id: str
    name: str | None
    parent_session_id: str | None
    created_at: str
    updated_at: str


def _session_to_response(session: Any) -> SessionResponse:
    """Convert a session object to SessionResponse.

    Args:
        session: The session from SessionStore

    Returns:
        SessionResponse instance
    """
    return SessionResponse(
        id=str(session.id),
        name=session.name,
        parent_session_id=str(session.parent_session_id) if session.parent_session_id else None,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
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
    tenant_id = str(current.tenant.id)
    parent_uuid = uuid.UUID(session_data.parent_session_id) if session_data.parent_session_id else None
    session = store.create_session(
        name=session_data.name or "Session",
        user_id=user_id,
        tenant_id=tenant_id,
        parent_session_id=parent_uuid,
    )

    return _session_to_response(session)


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
        _session_to_response(s)
        for s in sessions[offset : offset + limit]
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session: Any = Depends(get_session_or_404),
) -> SessionResponse:
    """Get a session by ID.

    Args:
        session: The session from get_session_or_404 dependency

    Returns:
        The session
    """
    return _session_to_response(session)


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_data: SessionUpdate,
    session: Any = Depends(get_session_or_404),
) -> SessionResponse:
    """Update a session.

    Args:
        session_data: The session data to update
        session: The session from get_session_or_404 dependency

    Returns:
        The updated session

    Raises:
        HTTPException: If session not found or access denied
    """
    kwargs = {}
    if session_data.name is not None:
        kwargs["name"] = session_data.name

    updated = get_store().update_session(session.id, **kwargs)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return _session_to_response(updated)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session: Any = Depends(get_session_or_404),
) -> None:
    """Delete a session.

    Args:
        session: The session from get_session_or_404 dependency

    Raises:
        HTTPException: If session not found or access denied
    """
    deleted = get_store().delete_session(session.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )


class LineageResponse(BaseModel):
    """Response model for session lineage."""

    id: str
    name: str | None
    parent_session_id: str | None
    lineage_depth: int
    created_at: str


@router.get("/{session_id}/lineage", response_model=list[LineageResponse])
async def get_session_lineage(
    session: Any = Depends(get_session_or_404),
    current: CurrentTenant = Depends(get_current_tenant),
) -> list[LineageResponse]:
    """Get the lineage (parent chain) of a session.

    Args:
        session: The session from get_session_or_404 dependency
        current: The current tenant

    Returns:
        List of sessions from root to current

    Raises:
        HTTPException: If session not found or access denied
    """
    store = get_store()
    lineage = store.get_lineage(session.id)

    if not lineage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    for s in lineage:
        _verify_session_tenant(s, current)

    return [
        LineageResponse(
            id=str(s.id),
            name=s.name,
            parent_session_id=str(s.parent_session_id) if s.parent_session_id else None,
            lineage_depth=getattr(s, "lineage_depth", 0),
            created_at=s.created_at.isoformat(),
        )
        for s in lineage
    ]


class SearchRequest(BaseModel):
    """Request model for search."""

    query: str
    limit: int = 10


class SearchResult(BaseModel):
    """Response model for search results."""

    message_id: str
    session_id: str
    content: str
    turn_index: int
    role: str


@router.post("/search", response_model=list[SearchResult])
async def search_messages(
    search_data: SearchRequest,
    current: CurrentTenant = Depends(get_current_tenant),
) -> list[SearchResult]:
    """Search messages across all sessions for the current tenant.

    Args:
        search_data: The search query
        current: The current tenant

    Returns:
        List of matching messages
    """
    store = get_store()

    search = SQLiteSearch()
    try:
        message_ids = search.search(store.engine, search_data.query, search_data.limit)
    except (OSError, ValueError) as exc:
        logger.error("Search failed: %s", exc, exc_info=True)
        return []

    results = []
    if message_ids:
        tenant_id = str(current.tenant.id)
        with store.get_db_session() as db:
            stmt = (
                select(Message)
                .join(SessionModel, Message.session_id == SessionModel.id)
                .where(Message.id.in_(message_ids))
                .where(SessionModel.tenant_id == tenant_id)
            )
            msgs = db.execute(stmt).scalars().all()
            for msg in msgs:
                results.append(
                    SearchResult(
                        message_id=str(msg.id),
                        session_id=str(msg.session_id),
                        content=msg.content[:200],
                        turn_index=msg.turn_index,
                        role=msg.role,
                    )
                )

    return results
