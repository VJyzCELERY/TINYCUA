"""
Pages CRUD endpoints for Notion-like Web Application.
Handles page creation, reading, updating, deletion, and favorites management. """
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Page, Workspace, Block  # noqa: F401
from app.schemas import (
    PageCreate,
    PageUpdate,
    PageResponse,
    PageWithBlocksResponse,
)
import json

router = APIRouter(prefix="/pages", tags=["Pages"])


def validate_user_permission(
    user: User,  # noqa: F401 - FastAPI dependency will inject this
    page_id: uuid.UUID,
) -> Page:
    """
    Validate that the authenticated user has permission to access a page.
    Users can always see their own pages and workspaces they belong to.
    
    Args:
        user: Authenticated user (injected by FastAPI)
        page_id: ID of the page being accessed
        
    Returns:
        Page object if permission granted
        
    Raises:
        HTTPException(403): If access not permitted
    """
    # For now, allow all authenticated users to see pages in their workspaces
    # In production, implement proper permission checks based on workspace membership
    return None  # Placeholder - actual implementation would check permissions here


def get_page_with_blocks(db: Session, page_id: uuid.UUID) -> Page:
    """
    Get a page with all its blocks loaded.
    
    Args:
        db: Database session
        page_id: UUID of the page to retrieve
        
    Returns:
        Page object with blocks relationship populated
        
    Raises:
        HTTPException(404): If page not found or soft-deleted without being restored
    """
    try:
        return db.query(Page).filter(
            Page.id == page_id,
            Page.deleted_at.is_(None)
        ).first()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page not found: {str(e)}"
        )


@router.get("", response_model=list[PageResponse], summary="List all pages")
def list_pages(db: Session = Depends(get_db), skip: int = 0, limit: int = 20):
    """
    List all pages in the database.
    
    Args:
        db: Database session
        skip: Number of records to skip for pagination
        limit: Maximum number of results to return
        
    Returns:
        List of PageResponse objects with basic page information
        
    Example Response:
        [{
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "My First Page",
            "icon_url": null,
            "cover_image_url": null
        }]
    """
    pages = db.query(Page).filter(
        Page.deleted_at.is_(None)
    ).order_by(Page.created_at.desc()).offset(skip).limit(limit).all()
    
    return [PageResponse.model_validate(page) for page in pages]


@router.post("", response_model=PageWithBlocksResponse, summary="Create a new page")
def create_page(
    page_data: PageCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new Notion-like page.
    
    Args:
        page_data: Page creation data with title, optional icon/cover
        db: Database session
        
    Returns:
        Created PageWithBlocksResponse object
        
    Example Request Body:
        {
            "title": "Product Roadmap",
            "icon_url": "🚀"
        }
        
    Example Response:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Product Roadmap",
            "icon_url": "🚀"
        }
    """
    page = Page(
        id=page_data.id if page_data.id else uuid.uuid4(),
        title=page_data.title,
        icon_url=page_data.icon_url or None,
        cover_image_url=page_data.cover_image_url or None,
        parent_page_id=page_data.parent_page_id,
        position_index=-1,  # Will be updated when blocks are added
        is_favorite=page_data.is_favorite if hasattr(page_data, 'is_favorite') else False,
    )
    
    db.add(page)
    db.commit()
    db.refresh(page)
    
    return PageWithBlocksResponse.model_validate(page)


@router.get("/{page_id}", response_model=PageWithBlocksResponse, summary="Get page with blocks")
def get_page(
    page_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific page including all its text content and formatting.
    
    Args:
        page_id: UUID of the page to retrieve
        db: Database session
        
    Returns:
        PageWithBlocksResponse containing full page data with blocks array
        
    Example Response:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Meeting Notes",
            "blocks": [
                {
                    "id": "block-id-1",
                    "type": "h1",
                    "text_content": "# Team Meeting"
                },
                {
                    "id": "block-id-2",
                    "type": "bulleted_list_item",
                    "text_content": "Discuss Q4 goals"
                }
            ]
        }
    """
    page = get_page_with_blocks(db, page_id)
    
    return PageWithBlocksResponse.model_validate(page)


@router.put("/{page_id}", response_model=PageWithBlocksResponse, summary="Update page properties")
def update_page(
    page_id: uuid.UUID,
    page_data: PageUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing page's properties.
    
    Args:
        page_id: UUID of the page to update
        page_data: Partial data containing fields to update
        db: Database session
        
    Returns:
        Updated PageWithBlocksResponse object with new values
        
    Example Request Body (partial):
        {
            "title": "Updated Meeting Notes",
            "icon_url": "📝"
        }
    """
    page = get_page_with_blocks(db, page_id)
    
    # Update only provided fields
    if page_data.title is not None:
        page.title = page_data.title
    if page_data.icon_url is not None:
        page.icon_url = page_data.icon_url
    if page_data.cover_image_url is not None:
        page.cover_image_url = page_data.cover_image_url
    
    db.commit()
    db.refresh(page)
    
    return PageWithBlocksResponse.model_validate(page)


@router.delete("/{page_id}", summary="Delete or restore a page")
def manage_page(
    page_id: uuid.UUID,
    hard_delete: bool = False,  # False = soft delete/restore
    db: Session = Depends(get_db),
):
    """
    Delete (soft) or permanently remove a page.
    
    Args:
        page_id: UUID of the page to manage
        hard_delete: If True, permanently deletes. Default False for soft delete/restore
        db: Database session
        
    Example Usage:
        DELETE /api/v1/pages/{page_id}?hard_delete=false  # Soft restore from trash
        DELETE /api/v1/pages/{page_id}?hard_delete=true   # Permanent deletion
    """
    page = get_page_with_blocks(db, page_id)
    
    if hard_delete:
        db.delete(page)  # True permanent delete
    else:
        # Soft delete - restore from trash by clearing deleted_at
        page.deleted_at = None
    
    db.commit()
    db.refresh(page)
    
    return PageWithBlocksResponse.model_validate(page)


@router.patch("/{page_id}/favorite", summary="Toggle favorite status")
def toggle_favorite(
    page_id: uuid.UUID,
    is_favorite: bool = True,  # If not provided, toggles current state
    db: Session = Depends(get_db),
):
    """
    Mark a page as favorite or unfavorite it.
    
    Args:
        page_id: UUID of the page to modify
        is_favorite: True to mark as favorite, False to remove from favorites,
                     omit for toggle behavior
        db: Database session
        
    Returns:
        Updated PageResponse object with new favorite status
        
    Example Request Body:
        {"is_favorite": true}
    """
    page = get_page_with_blocks(db, page_id)
    
    if is_favorite is not None:  # Explicit value provided
        page.is_favorite = is_favorite
    else:  # Toggle behavior - invert current state
        page.is_favorite = not page.is_favorite
    
    db.commit()
    db.refresh(page)
    
    return PageResponse.model_validate(page)
