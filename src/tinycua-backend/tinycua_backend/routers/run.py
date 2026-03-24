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
from tinycua_backend.models.tool import Tool

router = APIRouter(prefix="/v1/agents", tags=["run"])


class RunRequest(BaseModel):
    """Request model for running an agent."""

    user_input: str
    plan_mode: bool = False
    trace: bool = False
    verbose: bool = False
    stream_sse: bool = False


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

    This endpoint is stateless - it does not manage sessions or messages.
    Session and message management should be done via the /v1/sessions endpoints.

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
    config = get_config()
    tools_bundle = resolve_tools(agent.config.get("tools", []), tenant_id, db)

    runner_url = f"{config.runner.url}/internal/v1/run"
    headers = {"Authorization": f"Bearer {config.runner.token}"}

    async def event_generator():
        import json

        async with AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    runner_url,
                    headers=headers,
                    json={
                        "agent_config": agent.config,
                        "user_input": request.user_input,
                        "tools": tools_bundle,
                        "plan_mode": request.plan_mode,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line:
                            event_data = line
                            if not line.startswith("data:"):
                                try:
                                    event_data = json.dumps(json.loads(line))
                                except (json.JSONDecodeError, Exception):
                                    event_data = line
                            yield f"data: {event_data}\n\n"
            except Exception as e:
                import traceback

                traceback.print_exc()
                yield f"data: {{'error': '{str(e)}'}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
