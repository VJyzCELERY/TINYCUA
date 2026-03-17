"""Session API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth import CurrentTenant, get_current_tenant
from tinycua_backend.config import get_config
from tinycua_backend.database import get_db
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
    name: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str
    role: str
    content: str
    turn_index: int
    created_at: str


class SessionWithMessages(BaseModel):
    """Response model for a session with messages."""

    session: SessionResponse
    messages: list[MessageResponse]


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    agent_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SessionResponse]:
    """List all sessions for the current tenant.

    Args:
        current: The current tenant
        db: Database session
        agent_id: Optional agent ID to filter by
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of sessions
    """
    from tinycua_backend.storage.models import Session

    query = db.query(Session).filter(Session.tenant_id == str(current.tenant.id))

    if agent_id:
        query = query.filter(Session.agent_id == agent_id)

    sessions = query.offset(offset).limit(limit).all()

    return [
        SessionResponse(
            id=str(s.id),
            agent_id=str(s.agent_id),
            name=s.name,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionWithMessages)
async def get_session(
    session_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> SessionWithMessages:
    """Get a session with its messages.

    Args:
        session_id: The session ID
        current: The current tenant
        db: Database session

    Returns:
        The session with messages

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

    from tinycua_backend.storage.models import Session

    session = (
        db.query(Session)
        .filter(
            Session.id == uuid_session_id,
            Session.tenant_id == str(current.tenant.id),
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get messages from SessionStore
    config = get_config()
    store = SessionStore(config.database.url)
    messages = store.get_messages(uuid_session_id)

    return SessionWithMessages(
        session=SessionResponse(
            id=str(session.id),
            agent_id=str(session.agent_id),
            name=session.name,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
        ),
        messages=[
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                turn_index=m.turn_index,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )
