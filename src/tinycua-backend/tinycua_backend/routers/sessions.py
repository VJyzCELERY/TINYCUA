"""Session API routes using SessionStore for persistence."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from tinycua_backend.auth import CurrentTenant, get_current_tenant
from tinycua_backend.config import get_config
from tinycua_sdk.storage import SessionStore

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    """Request model for creating a session."""

    agent_id: str
    name: str | None = None


class SessionResponse(BaseModel):
    """Response model for a session."""

    id: str
    agent_id: str
    name: str | None
    created_at: str
    updated_at: str


class MessageCreate(BaseModel):
    """Request model for creating a message."""

    role: str
    content: str


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str
    role: str
    content: str
    turn_index: int
    created_at: str


def get_store() -> SessionStore:
    """Get SessionStore instance."""
    config = get_config()
    return SessionStore(config.database.url)


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
    session = store.create_session(
        name=session_data.name or "Session",
        user_id=str(current.tenant.id),
    )

    return SessionResponse(
        id=str(session.id),
        agent_id=session_data.agent_id,
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
    sessions = store.list_sessions(user_id=str(current.tenant.id))

    return [
        SessionResponse(
            id=str(s.id),
            agent_id="",
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
        HTTPException: If session not found
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

    return SessionResponse(
        id=str(session.id),
        agent_id="",
        name=session.name,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
    )


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    session_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
    limit: int = 100,
    offset: int = 0,
) -> list[MessageResponse]:
    """List messages for a session.

    Args:
        session_id: The session ID
        current: The current tenant
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of messages

    Raises:
        HTTPException: If session not found
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

    messages = store.get_messages(uuid_session_id, limit=limit)
    messages = messages[offset : offset + limit]

    return [
        MessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            turn_index=m.turn_index,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    session_id: str,
    message_data: MessageCreate,
    current: CurrentTenant = Depends(get_current_tenant),
) -> MessageResponse:
    """Add a message to a session.

    Args:
        session_id: The session ID
        message_data: The message data
        current: The current tenant

    Returns:
        The created message

    Raises:
        HTTPException: If session not found
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

    message = store.add_message(
        session_id=uuid_session_id,
        role=message_data.role,
        content=message_data.content,
    )

    return MessageResponse(
        id=str(message.id),
        role=message.role,
        content=message.content,
        turn_index=message.turn_index,
        created_at=message.created_at.isoformat(),
    )
