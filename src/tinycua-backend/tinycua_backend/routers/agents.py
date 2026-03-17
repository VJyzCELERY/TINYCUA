"""Agent API routes."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth import CurrentTenant, get_current_tenant, get_tenant_filter
from tinycua_backend.database import get_db
from tinycua_backend.models.agent import Agent

router = APIRouter(prefix="/v1/agents", tags=["agents"])


class AgentCreate(BaseModel):
    """Request model for creating an agent."""

    name: str
    config: dict[str, Any]


class AgentUpdate(BaseModel):
    """Request model for updating an agent."""

    name: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    """Response model for an agent."""

    id: str
    name: str
    config: dict[str, Any]
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, agent: Agent) -> "AgentResponse":
        """Create response from ORM model."""
        return cls(
            id=str(agent.id),
            name=agent.name,
            config=agent.config,
            is_active=agent.is_active,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat(),
        )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Create a new agent.

    Args:
        agent_data: The agent data
        current: The current tenant
        db: Database session

    Returns:
        The created agent
    """
    agent = Agent(
        tenant_id=str(current.tenant.id),
        name=agent_data.name,
        config=agent_data.config,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return AgentResponse.from_orm(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
) -> list[AgentResponse]:
    """List all agents for the current tenant.

    Args:
        current: The current tenant
        db: Database session
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of agents
    """
    query = db.query(Agent)
    tenant_filter = get_tenant_filter(current.tenant, Agent)
    if tenant_filter:
        query = query.filter(tenant_filter)

    agents = query.offset(offset).limit(limit).all()
    return [AgentResponse.from_orm(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Get an agent by ID.

    Args:
        agent_id: The agent ID
        current: The current tenant
        db: Database session

    Returns:
        The agent

    Raises:
        HTTPException: If agent not found
    """
    try:
        uuid_agent_id = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID",
        )

    query = db.query(Agent).filter(Agent.id == uuid_agent_id)
    tenant_filter = get_tenant_filter(current.tenant, Agent)
    if tenant_filter:
        query = query.filter(tenant_filter)

    agent = query.first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return AgentResponse.from_orm(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Update an agent.

    Args:
        agent_id: The agent ID
        agent_data: The agent data to update
        current: The current tenant
        db: Database session

    Returns:
        The updated agent

    Raises:
        HTTPException: If agent not found
    """
    try:
        uuid_agent_id = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID",
        )

    query = db.query(Agent).filter(Agent.id == uuid_agent_id)
    tenant_filter = get_tenant_filter(current.tenant, Agent)
    if tenant_filter:
        query = query.filter(tenant_filter)

    agent = query.first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent_data.name is not None:
        agent.name = agent_data.name
    if agent_data.config is not None:
        agent.config = agent_data.config
    if agent_data.is_active is not None:
        agent.is_active = agent_data.is_active

    db.commit()
    db.refresh(agent)
    return AgentResponse.from_orm(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> None:
    """Delete an agent.

    Args:
        agent_id: The agent ID
        current: The current tenant
        db: Database session

    Raises:
        HTTPException: If agent not found
    """
    try:
        uuid_agent_id = uuid.UUID(agent_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID",
        )

    query = db.query(Agent).filter(Agent.id == uuid_agent_id)
    tenant_filter = get_tenant_filter(current.tenant, Agent)
    if tenant_filter:
        query = query.filter(tenant_filter)

    agent = query.first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    db.delete(agent)
    db.commit()
