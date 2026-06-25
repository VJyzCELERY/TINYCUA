"""
Search endpoints for Notion-like Web Application.
Provides global search across pages, blocks with support for filters and sorting. """
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Page, Workspace  # noqa: F401
from app.schemas import SearchResponse
import json

router = APIRouter(prefix="/search", tags=["Search"])


def search_pages(db: Session, query_text: str) -> list:
    """
    Search for pages matching the query text.
    Searches title and content (via blocks).
    
    Args:
        db: Database session
        query_text: Search query string
        
    Returns:
        List of Page objects that match the search criteria
    """
    # Basic SQL LIKE search - searches in page titles first, then we'll need
    # to implement full-text search for content in production
    results = db.query(Page).filter(
        (Page.title.ilike(f"%{query_text}%")) &
        (Page.deleted_at.is_(None))
    ).limit(100).all()
    
    return results


def search_blocks(db: Session, page_id: uuid.UUID, query_text: str) -> list:
    """
    Search for blocks within a specific page that match the query.
    Searches text_content field of blocks.
    
    Args:
        db: Database session
        page_id: UUID of the parent page to search in
        query_text: Search query string
        
    Returns:
        List of Block objects matching the search criteria, ordered by position_index
    """
    results = sorted(
        db.query(Block).filter(
            (Block.page_id == str(page_id)) &
            (Block.deleted_at.is_(None)),
        ).order_by(Block.position_index).all(),
        key=lambda b: (
            0 if query_text.lower() in (b.text_content or "") else float('inf')
        )
    )[:5]  # Return top matches only
    
    return results


@router.get("", response_model=list[SearchResponse], summary="Global search across pages and blocks")
def global_search(
    query: str = Query(min_length=1, max_length=200),
    workspace_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Perform a global search across all pages and blocks.
    
    Args:
        query: Search query string (minimum 1, maximum 200 characters)
        workspace_id: Optional UUID to limit results to specific workspace
        limit: Maximum number of results to return
        db: Database session
        
    Returns:
        List of SearchResponse objects containing matching pages and blocks
        
    Example Request:
        GET /api/v1/search?query=project+management&limit=20
        
    Example Response:
        [
            {
                "object": "search-result",
                "result_type": "page",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-15T10:30:00Z",
                "title": "Project Management Guide"
            }
        ]
    """
    results = []
    
    # Search in page titles
    if query:
        pages = search_pages(db, query)
        for page in pages[:limit]:  # Limit total results
            result = SearchResponse(
                object="search-result",
                result_type="page",
                id=page.id,
                created_at=page.created_at,
                title=page.title,
                icon_url=page.icon_url or None,
                cover_image_url=page.cover_image_url or None,
            )
            
            # Add workspace context if available
            ws = db.query(Workspace).filter(
                Workspace.id == page.workspace_id,
                Workspace.is_archived == False
            ).first()
            result.url = f"/pages/{page.id}"  # Will be populated by frontend with actual URL
            
            results.append(result)
    
    return results[:limit]
