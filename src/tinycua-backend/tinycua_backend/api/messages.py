"""Message API routes using SessionStore for persistence."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from tinycua_backend.auth.core import CurrentTenant, get_current_tenant
from tinycua_backend.api.sessions import _verify_session_tenant, get_store

router = APIRouter(prefix="/v1/sessions", tags=["messages"])


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
