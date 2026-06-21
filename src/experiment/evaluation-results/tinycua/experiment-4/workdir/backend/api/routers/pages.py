"""API endpoints for Notion-like app - Pages CRUD with real database integration."""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.database import get_db
from backend.models.schema import Page, Block, Document


@router.get("/pages", response_model=List[dict])
def list_pages(db: Session = Depends(get_db)):
    """List all pages for the current user with real database queries."""
    # Query pages from SQLite database
    pages = db.query(Page).all()
    
    result = []
    for page in pages:
        # Get blocks content for this page
        blocks = db.query(Block).filter(Block.page_id == page.id).all()
        
        page_data = {
            "id": str(page.id),  # Use string IDs to match frontend expectations
            "title": page.title or "Untitled",
            "cover_image": page.cover_image_url,
            "breadcrumbs": [],
            "content": [
                {"type": block.block_type or "paragraph", "text": block.text_content}
                for block in blocks
            ],
            "position_index": page.position_index,
            "is_favorite": page.is_favorite,
        }
        
        # Add document info if available
        doc = db.query(Document).filter(Document.id == page.document_id).first()
        if doc:
            page_data["document"] = {
                "id": str(doc.id),
                "title": doc.title
            }
        
        result.append(page_data)
    
    return result


@router.post("/pages", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_page(
    title: Optional[str] = None,
    content: Optional[List[dict]] = None,
    cover_image_url: Optional[str] = None,
    document_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Create a new page with real database persistence."""
    
    # Generate unique ID based on existing pages count
    last_page = db.query(Page).order_by(Page.id.desc()).first()
    new_page_id = (last_page.id + 1) if last_page else 1
    
    # Create page from database model
    new_page = Page(
        id=new_page_id,
        title=title or "Untitled",
        cover_image_url=cover_image_url,
        position_index=len([p for p in db.query(Page).all()]),
        is_favorite=False
    )
    
    # If document_id provided, associate with document
    if document_id:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            new_page.document_id = doc.id
    
    try:
        db.add(new_page)
        db.commit()
        db.refresh(new_page)
        
        # Save content blocks if provided
        if content:
            for i, block_data in enumerate(content):
                block_text = block_data.get("text", "")
                block_type = block_data.get("type", "paragraph")
                
                new_block = Block(
                    id=new_page_id * 10 + (i + 1),
                    page_id=new_page.id,
                    block_type=block_type,
                    text_content=block_text
                )
                db.add(new_block)
            
            db.commit()
        
        # Return page data matching frontend API contract
        blocks = db.query(Block).filter(Block.page_id == new_page.id).all()
        
        return {
            "id": str(new_page.id),
            "title": new_page.title,
            "cover_image": new_page.cover_image_url,
            "breadcrumbs": [],
            "content": [
                {"type": b.block_type or "paragraph", "text": b.text_content}
                for b in blocks
            ],
            "position_index": new_page.position_index,
            "is_favorite": new_page.is_favorite,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pages/{page_id}", response_model=dict)
def get_page(page_id: int, db: Session = Depends(get_db)):
    """Get a single page by ID with real database query."""
    # Convert to string for comparison (frontend sends strings)
    page = db.query(Page).filter(Page.id == str(page_id)).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Get blocks content
    blocks = db.query(Block).filter(Block.page_id == page.id).all()
    
    return {
        "id": str(page.id),
        "title": page.title or "",
        "cover_image": page.cover_image_url,
        "breadcrumbs": [],
        "content": [
            {"type": b.block_type or "paragraph", "text": b.text_content}
            for b in blocks
        ],
        "position_index": page.position_index,
        "is_favorite": page.is_favorite,
    }


@router.put("/pages/{page_id}", response_model=dict)
def update_page(
    page_id: int,
    title: Optional[str] = None,
    content: Optional[List[dict]] = None,
    cover_image_url: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update an existing page with real database persistence."""
    # Convert to string for comparison
    page = db.query(Page).filter(Page.id == str(page_id)).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    try:
        # Update fields
        if title is not None:
            page.title = title
        if cover_image_url is not None:
            page.cover_image_url = cover_image_url
        
        db.commit()
        db.refresh(page)
        
        # Handle content update - delete old blocks and add new ones
        if content is not None:
            # Delete existing blocks for this page
            db.query(Block).filter(Block.page_id == page.id).delete()
            
            # Add new blocks
            for i, block_data in enumerate(content):
                block_text = block_data.get("text", "")
                block_type = block_data.get("type", "paragraph")
                
                new_block = Block(
                    id=page.id * 10 + (i + 1),
                    page_id=page.id,
                    block_type=block_type,
                    text_content=block_text
                )
                db.add(new_block)
            
            db.commit()
        
        # Return updated page data
        blocks = db.query(Block).filter(Block.page_id == page.id).all()
        
        return {
            "id": str(page.id),
            "title": page.title,
            "cover_image": page.cover_image_url,
            "breadcrumbs": [],
            "content": [
                {"type": b.block_type or "paragraph", "text": b.text_content}
                for b in blocks
            ],
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pages/{page_id}", response_model=dict)
def delete_page(page_id: int, db: Session = Depends(get_db)):
    """Delete a page by ID with real database persistence."""
    # Convert to string for comparison
    page = db.query(Page).filter(Page.id == str(page_id)).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    try:
        # Delete associated blocks first (cascade will handle it)
        db.query(Block).filter(Block.page_id == page.id).delete()
        
        # Delete the page
        db.delete(page)
        db.commit()
        
        return {"message": f"Page {page_id} deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# Cover image endpoint
@router.post("/pages/{page_id}/cover", response_model=dict)
def set_cover_image(
    page_id: int,
    url: str,
    db: Session = Depends(get_db)
):
    """Set cover image for a page with real database persistence."""
    # Convert to string for comparison
    page = db.query(Page).filter(Page.id == str(page_id)).first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    try:
        page.cover_image_url = url
        db.commit()
        
        return {
            "id": str(page.id),
            "cover_image": url
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
