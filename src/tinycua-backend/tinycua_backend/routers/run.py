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


def load_agent(agent_id: str, tenant_id: str, db: Session) -> Agent:
    """Load and validate agent.

    Args:
        agent_id: Agent ID string
        tenant_id: Tenant ID
        db: Database session

    Returns:
        Agent model

    Raises:
        HTTPException: If agent not found or invalid
    """
    try:
        uuid_agent_id = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID",
        )

    agent = (
        db.query(Agent)
        .filter(
            Agent.id == uuid_agent_id,
            Agent.tenant_id == tenant_id,
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

    return agent


def load_or_create_session(
    session_id: str | None,
    session_name: str | None,
    agent_id: str,
    tenant_id: str,
    db: Session,
) -> str:
    """Load or create a session.

    Args:
        session_id: Optional session ID
        session_name: Optional session name
        agent_id: Agent ID
        tenant_id: Tenant ID
        db: Database session

    Returns:
        Session ID
    """
    if session_id:
        try:
            uuid_session_id = uuid.UUID(session_id)
            session = (
                db.query(BackendSession)
                .filter(
                    BackendSession.id == uuid_session_id,
                    BackendSession.tenant_id == tenant_id,
                )
                .first()
            )
            if session:
                return session.id
        except ValueError:
            pass

    session = BackendSession(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=session_name or "Session",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session.id


def get_session_messages(session_id: str, db_url: str) -> list[dict]:
    """Get messages from session store.

    Args:
        session_id: Session ID
        db_url: Database URL

    Returns:
        List of message dicts
    """
    try:
        store = SessionStore(db_url)
        messages = store.get_messages(session_id)
        return [{"role": m.role, "content": m.content} for m in messages]
    except Exception as e:
        print(f"Warning: Could not get messages from SessionStore: {e}")
        return []


def resolve_tools(tool_configs: list, tenant_id: str, db: Session) -> list[dict]:
    """Resolve tools from agent config.

    Args:
        tool_configs: Tool configurations from agent
        tenant_id: Tenant ID
        db: Database session

    Returns:
        List of tool bundles
    """
    agent_tool_names = []
    for t in tool_configs:
        if isinstance(t, dict):
            agent_tool_names.append(t.get("name", ""))
        elif isinstance(t, str):
            agent_tool_names.append(t)

    if not agent_tool_names:
        return []

    tools = (
        db.query(Tool)
        .filter(
            Tool.tenant_id == tenant_id,
            Tool.name.in_(agent_tool_names),
            Tool.is_active,
        )
        .all()
    )

    if not tools:
        return []

    return resolve_tool_dependencies(tools, db, tenant_id)


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
    tenant_id = str(current.tenant.id)

    agent = load_agent(agent_id, tenant_id, db)
    session_id = load_or_create_session(
        request.session_id,
        request.session_name,
        str(agent.id),
        tenant_id,
        db,
    )

    config = get_config()
    messages_data = get_session_messages(str(session_id), config.database.url)
    tools_bundle = resolve_tools(agent.config.get("tools", []), tenant_id, db)

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
