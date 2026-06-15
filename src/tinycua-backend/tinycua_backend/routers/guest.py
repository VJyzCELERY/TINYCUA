"""Guest API routes for unauthenticated agent execution."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth import GuestTenant, get_guest_tenant
from tinycua_backend.config import get_config
from tinycua_backend.database import get_db
from tinycua_backend.guest import get_guest_session_store
from tinycua_backend.models.agent import Agent

router = APIRouter(prefix="/guest", tags=["guest"])


class GuestRunRequest(BaseModel):
    """Request model for guest agent execution."""

    agent_id: str
    user_input: str
    session_id: str | None = None


@router.post("/run")
async def guest_run_agent(
    request: GuestRunRequest,
    guest: GuestTenant = Depends(get_guest_tenant),
    db: Session = Depends(get_db),
):
    """Execute an agent as a guest (no auth required).

    Guest sessions are:
    - Temporary (in-memory, not persisted)
    - Shared among all guest users
    - Auto-expire after 30 minutes of inactivity

    Args:
        request: The run request
        guest: The guest tenant
        db: Database session

    Returns:
        Streaming response with SSE events
    """
    # Validate agent_id
    try:
        uuid_agent_id = uuid.UUID(request.agent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID",
        )

    # Load agent (from guest tenant)
    agent = (
        db.query(Agent)
        .filter(
            Agent.id == uuid_agent_id,
            Agent.tenant_id == str(guest.tenant.id),
        )
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is not active",
        )

    # Get or create guest session
    store = get_guest_session_store()
    session_id = request.session_id

    if session_id:
        session = store.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or expired",
            )
    else:
        session_id = store.create_session(
            agent_id=str(agent.id),
            metadata={"user_agent": "guest"},
        )

    session = store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session",
        )

    # Add user message to session
    session.add_message(role="user", content=request.user_input)
    messages_data = session.get_messages()

    # Get config
    config = get_config()

    # Load tools from agent config
    tools_bundle: list[dict] = []
    agent_tool_names = agent.config.get("tools", [])

    if agent_tool_names:
        from tinycua_backend.models.tool import Tool

        tools = (
            db.query(Tool)
            .filter(
                Tool.tenant_id == str(guest.tenant.id),
                Tool.name.in_(agent_tool_names),
                Tool.is_active,
            )
            .all()
        )

        if tools:
            from tinycua_backend.routers.run import resolve_tool_dependencies

            tools_bundle = resolve_tool_dependencies(tools, db, str(guest.tenant.id))

    # Call runner
    runner_url = f"{config.runner.url}/internal/v1/run"
    headers = {"Authorization": f"Bearer {config.runner.token}"}

    async def event_generator():
        try:
            async with AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    runner_url,
                    headers=headers,
                    json={
                        "agent_config": agent.config,
                        "session_id": session_id,
                        "db_url": config.database.url,
                        "user_input": request.user_input,
                        "messages": messages_data,
                        "tools": tools_bundle,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            yield f"{line}\n\n"
        except Exception as e:
            import traceback

            traceback.print_exc()
            yield f"data: {{'error': '{str(e)}'}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
