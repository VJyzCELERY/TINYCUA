"""Run API routes for agent execution."""

import uuid
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth import CurrentTenant, get_current_tenant
from tinycua_backend.config import get_config
from tinycua_backend.database import get_db
from tinycua_backend.models.agent import Agent
from tinycua_backend.models.session import Session as BackendSession
from tinycua_backend.models.tool import Tool
from tinycua_sdk.storage import SessionStore

router = APIRouter(prefix="/v1/agents", tags=["run"])


class RunRequest(BaseModel):
    """Request model for running an agent."""

    user_input: str
    session_id: str | None = None
    session_name: str | None = None


def resolve_tool_dependencies(
    tools: list[Tool],
    db: Session,
    tenant_id: str,
) -> list[dict]:
    """Resolve all tool dependencies from database.

    Args:
        tools: List of Tool models
        db: Database session
        tenant_id: Tenant ID for filtering

    Returns:
        List of tool bundles including dependencies
    """
    tool_map: dict[str, Tool] = {t.name: t for t in tools}
    resolved_names: set[str] = set()
    result: list[dict] = []
    queue: deque[Tool] = deque(tools)

    while queue:
        tool = queue.popleft()

        if tool.name in resolved_names:
            continue

        for dep in tool.tool_dependencies:
            dep_name = dep.get("name", "")
            if dep_name and dep_name not in resolved_names and dep_name in tool_map:
                queue.append(tool_map[dep_name])

        result.append(
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "source": tool.source,
                "external_dependencies": tool.external_dependencies or [],
                "tool_dependencies": tool.tool_dependencies or [],
                "version": tool.version,
            }
        )
        resolved_names.add(tool.name)

    return result


@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    request: RunRequest,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Execute an agent and stream results.

    Args:
        agent_id: The agent ID
        request: The run request
        current: The current tenant
        db: Database session

    Returns:
        Streaming response with SSE events
    """
    try:
        uuid_agent_id = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID",
        )

    # Load agent
    agent = (
        db.query(Agent)
        .filter(
            Agent.id == uuid_agent_id,
            Agent.tenant_id == str(current.tenant.id),
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

    # Load or create session
    session_id = None
    if request.session_id:
        try:
            uuid_session_id = uuid.UUID(request.session_id)
            session = (
                db.query(BackendSession)
                .filter(
                    BackendSession.id == uuid_session_id,
                    BackendSession.tenant_id == str(current.tenant.id),
                )
                .first()
            )
            if session:
                session_id = session.id
        except ValueError:
            pass

    if not session_id:
        session = BackendSession(
            tenant_id=str(current.tenant.id),
            agent_id=str(agent.id),
            name=request.session_name or "Session",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

    # Get config
    config = get_config()

    # Get messages from SessionStore (optional - may fail if tables don't exist)
    messages_data = []
    try:
        store = SessionStore(config.database.url)
        messages = store.get_messages(session_id)
        messages_data = [{"role": m.role, "content": m.content} for m in messages]
    except Exception as e:
        print(f"Warning: Could not get messages from SessionStore: {e}")

    # Load tools from agent config and resolve dependencies
    tools_bundle: list[dict] = []
    agent_tool_configs = agent.config.get("tools", [])

    # Extract tool names from tool config dicts
    agent_tool_names = []
    for t in agent_tool_configs:
        if isinstance(t, dict):
            agent_tool_names.append(t.get("name", ""))
        elif isinstance(t, str):
            agent_tool_names.append(t)

    if agent_tool_names:
        tools = (
            db.query(Tool)
            .filter(
                Tool.tenant_id == str(current.tenant.id),
                Tool.name.in_(agent_tool_names),
                Tool.is_active,
            )
            .all()
        )

        if tools:
            tools_bundle = resolve_tool_dependencies(tools, db, str(current.tenant.id))

    # Call runner
    runner_url = f"{config.runner.url}/internal/v1/run"
    headers = {"Authorization": f"Bearer {config.runner.token}"}

    async def event_generator():
        async with AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    runner_url,
                    headers=headers,
                    json={
                        "agent_config": agent.config,
                        "session_id": str(session_id),
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
