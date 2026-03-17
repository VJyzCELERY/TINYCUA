"""Tool API routes."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tinycua_backend.auth import CurrentTenant, get_current_tenant
from tinycua_backend.database import get_db
from tinycua_backend.models.tool import Tool

router = APIRouter(prefix="/v1/tools", tags=["tools"])


class ToolCreate(BaseModel):
    """Request model for creating a tool."""

    name: str
    description: str | None = None
    source: str
    parameters: dict[str, Any] = {}
    external_dependencies: list[str] = []
    tool_dependencies: list[dict[str, Any]] = []
    version: str


class ToolUpdate(BaseModel):
    """Request model for updating a tool."""

    name: str | None = None
    description: str | None = None
    source: str | None = None
    parameters: dict[str, Any] | None = None
    external_dependencies: list[str] | None = None
    tool_dependencies: list[dict[str, Any]] | None = None
    version: str | None = None
    is_active: bool | None = None


class ToolResponse(BaseModel):
    """Response model for a tool."""

    id: str
    name: str
    description: str | None
    source: str
    parameters: dict[str, Any]
    external_dependencies: list[str]
    tool_dependencies: list[dict[str, Any]]
    version: str
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, tool: Tool) -> "ToolResponse":
        """Create response from ORM model."""
        return cls(
            id=str(tool.id),
            name=tool.name,
            description=tool.description,
            source=tool.source,
            parameters=tool.parameters,
            external_dependencies=tool.external_dependencies or [],
            tool_dependencies=tool.tool_dependencies or [],
            version=tool.version,
            is_active=tool.is_active,
            created_at=tool.created_at.isoformat(),
            updated_at=tool.updated_at.isoformat(),
        )


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tool_data: ToolCreate,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ToolResponse:
    """Create a new tool.

    Args:
        tool_data: The tool data
        current: The current tenant
        db: Database session

    Returns:
        The created tool
    """
    existing = (
        db.query(Tool)
        .filter(
            Tool.tenant_id == str(current.tenant.id),
            Tool.name == tool_data.name,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{tool_data.name}' already exists",
        )

    tool = Tool(
        tenant_id=str(current.tenant.id),
        name=tool_data.name,
        description=tool_data.description,
        source=tool_data.source,
        parameters=tool_data.parameters,
        external_dependencies=tool_data.external_dependencies,
        tool_dependencies=tool_data.tool_dependencies,
        version=tool_data.version,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return ToolResponse.from_orm(tool)


@router.get("", response_model=list[ToolResponse])
async def list_tools(
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
) -> list[ToolResponse]:
    """List all tools for the current tenant.

    Args:
        current: The current tenant
        db: Database session
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of tools
    """
    tools = (
        db.query(Tool)
        .filter(Tool.tenant_id == str(current.tenant.id))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [ToolResponse.from_orm(t) for t in tools]


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ToolResponse:
    """Get a tool by ID.

    Args:
        tool_id: The tool ID
        current: The current tenant
        db: Database session

    Returns:
        The tool

    Raises:
        HTTPException: If tool not found
    """
    try:
        uuid_tool_id = uuid.UUID(tool_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tool ID",
        )

    tool = (
        db.query(Tool)
        .filter(
            Tool.id == uuid_tool_id,
            Tool.tenant_id == str(current.tenant.id),
        )
        .first()
    )

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    return ToolResponse.from_orm(tool)


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    tool_data: ToolUpdate,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ToolResponse:
    """Update a tool.

    Args:
        tool_id: The tool ID
        tool_data: The tool data to update
        current: The current tenant
        db: Database session

    Returns:
        The updated tool

    Raises:
        HTTPException: If tool not found
    """
    try:
        uuid_tool_id = uuid.UUID(tool_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tool ID",
        )

    tool = (
        db.query(Tool)
        .filter(
            Tool.id == uuid_tool_id,
            Tool.tenant_id == str(current.tenant.id),
        )
        .first()
    )

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    if tool_data.name is not None:
        tool.name = tool_data.name
    if tool_data.description is not None:
        tool.description = tool_data.description
    if tool_data.source is not None:
        tool.source = tool_data.source
    if tool_data.parameters is not None:
        tool.parameters = tool_data.parameters
    if tool_data.external_dependencies is not None:
        tool.external_dependencies = tool_data.external_dependencies
    if tool_data.tool_dependencies is not None:
        tool.tool_dependencies = tool_data.tool_dependencies
    if tool_data.version is not None:
        tool.version = tool_data.version
    if tool_data.is_active is not None:
        tool.is_active = tool_data.is_active

    db.commit()
    db.refresh(tool)
    return ToolResponse.from_orm(tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> None:
    """Delete a tool.

    Args:
        tool_id: The tool ID
        current: The current tenant
        db: Database session

    Raises:
        HTTPException: If tool not found
    """
    try:
        uuid_tool_id = uuid.UUID(tool_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tool ID",
        )

    tool = (
        db.query(Tool)
        .filter(
            Tool.id == uuid_tool_id,
            Tool.tenant_id == str(current.tenant.id),
        )
        .first()
    )

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    db.delete(tool)
    db.commit()
