"""
Workspace CRUD endpoints for Notion-like Web Application.
Handles workspace management including creation, reading, updating, deletion, and member operations. """
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Workspace  # noqa: F401
from app.schemas import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
)
import json

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


def get_workspace(db: Session, workspace_id: uuid.UUID) -> Optional[Workspace]:
    """
    Get a specific workspace by ID.
    
    Args:
        db: Database session
        workspace_id: UUID of the workspace to retrieve
        
    Returns:
        Workspace object or None if not found
    """
    return db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.is_archived == False  # Don't show archived workspaces by default
    ).first()


def get_or_create_default_workspace(db: Session, user: User) -> Workspace:
    """
    Get the default workspace for a user or create one if it doesn't exist.
    
    Args:
        db: Database session
        user: Authenticated user
        
    Returns:
        Default Workspace object
    """
    # Try to get existing default workspace
    default_ws = db.query(Workspace).filter(
        Workspace.owner_id == str(user.id),
        Workspace.name == f"{user.username or 'User'}'s Space"
    ).first()
    
    if not default_ws:
        # Create new default workspace
        ws = Workspace(
            id=uuid.uuid4(),
            name=f"{user.username}'s Space",
            description="Your personal workspace",
            color="#007AFF"
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
    
    return default_ws


@router.get("", response_model=list[WorkspaceResponse], summary="List all workspaces")
def list_workspaces(
    skip: int = 0,
    limit: Optional[int] = None,  # None means no limit (all workspaces)
    db: Session = Depends(get_db),
):
    """
    List all active workspaces.
    
    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of results (None = no limit)
        db: Database session
        
    Returns:
        List of WorkspaceResponse objects ordered by created_at desc
        
    Example Response:
        [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Product Development",
                "description": "Workspace for product team"
            }
        ]
    """
    workspaces = db.query(Workspace).filter(
        Workspace.is_archived == False
    ).order_by(Workspace.created_at.desc()).offset(skip)
    
    if limit is not None:
        workspaces = workspaces.limit(limit).all()
    else:
        workspaces = workspaces.all()
    
    return [WorkspaceResponse.model_validate(ws) for ws in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceResponse, summary="Get a workspace")
def get_workspace(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific workspace by ID.
    
    Args:
        workspace_id: UUID of the workspace to retrieve
        db: Database session
        
    Returns:
        WorkspaceResponse object with full workspace data including page count
        
    Raises:
        HTTPException(404): If workspace not found or archived
    """
    ws = get_workspace(db, workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found."
        )
    
    # Count pages in this workspace
    page_count = db.query(Page).filter(
        Page.workspace_id == str(workspace_id),
        Page.deleted_at.is_(None)
    ).count()
    
    ws_response = WorkspaceResponse.model_validate(ws)
    ws_response.page_count = page_count  # Add computed field for frontend
    
    return ws_response


@router.post("", response_model=WorkspaceResponse, summary="Create a new workspace")
def create_workspace(
    workspace_data: WorkspaceCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new Notion-like workspace.
    
    Args:
        workspace_data: Workspace creation data with name, description, etc.
        db: Database session
        
    Returns:
        Created WorkspaceResponse object
        
    Example Request Body:
        {
            "name": "Engineering Team",
            "description": "Workspace for engineering projects"
        }
        
    Example Response:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Engineering Team",
            "description": "Workspace for engineering projects"
        }
    """
    ws = Workspace(
        id=workspace_data.id if workspace_data.id else uuid.uuid4(),
        name=workspace_data.name,
        description=workspace_data.description or None,
        icon_url=workspace_data.icon_url or None,
        cover_image_url=workspace_data.cover_image_url or None,
        color=workspace_data.color or "#007AFF"
    )
    
    db.add(ws)
    db.commit()
    db.refresh(ws)
    
    return WorkspaceResponse.model_validate(ws)


@router.put("/{workspace_id}", response_model=WorkspaceResponse, summary="Update a workspace")
def update_workspace(
    workspace_id: uuid.UUID,
    workspace_data: WorkspaceUpdate = None,
    db: Session = Depends(get_db),
):
    """
    Update an existing workspace's properties.
    
    Args:
        workspace_id: UUID of the workspace to update
        workspace_data: Partial data containing fields to update
        db: Database session
        
    Returns:
        Updated WorkspaceResponse object with new values
        
    Example Request Body (partial):
        {
            "name": "Updated Engineering Team",
            "color": "#FF6B00"
        }
    """
    if workspace_data is None:
        return get_workspace(db, workspace_id)
    
    ws = get_workspace(db, workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found."
        )
    
    # Update only provided fields
    if workspace_data.name is not None:
        ws.name = workspace_data.name
    if workspace_data.description is not None:
        ws.description = workspace_data.description
    if workspace_data.icon_url is not None:
        ws.icon_url = workspace_data.icon_url
    if workspace_data.cover_image_url is not None:
        ws.cover_image_url = workspace_data.cover_image_url
    if workspace_data.color is not None:
        ws.color = workspace_data.color
    
    db.commit()
    db.refresh(ws)
    
    return WorkspaceResponse.model_validate(ws)


@router.delete("/{workspace_id}", summary="Delete or archive a workspace")
def manage_workspace(
    workspace_id: uuid.UUID,
    hard_delete: bool = False,  # Default False for soft delete/archive
    db: Session = Depends(get_db),
):
    """
    Archive (soft delete) or permanently remove a workspace.
    
    Args:
        workspace_id: UUID of the workspace to manage
        hard_delete: If True, permanently deletes. Default False for soft archive
        db: Database session
        
    Note:
        Workspaces with pages will be archived (not deleted) unless explicitly requested.
        This protects against accidental data loss.
        
    Example Usage:
        DELETE /api/v1/workspaces/{workspace_id}?hard_delete=false  # Archive workspace
        DELETE /api/v1/workspaces/{workspace_id}?hard_delete=true   # Permanent deletion (dangerous!)
    """
    ws = get_workspace(db, workspace_id)
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found."
        )
    
    # If hard delete and has pages, warn but still allow
    page_count = db.query(Page).filter(
        Page.workspace_id == str(workspace_id),
        Page.deleted_at.is_(None)
    ).count()
    
    if page_count > 0 and not hard_delete:
        ws.is_archived = True  # Archive instead of delete
    else:
        db.delete(ws)  # Hard delete or archive empty workspace
    
    db.commit()
    db.refresh(ws)
    
    return WorkspaceResponse.model_validate(ws)
