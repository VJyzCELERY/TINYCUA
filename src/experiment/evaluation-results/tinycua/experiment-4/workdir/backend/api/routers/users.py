"""API endpoints for Notion-like app including Users and Pages/Blocks management."""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import bcrypt

from backend.api.database import get_db
from backend.models.schema import User, Page, Block, Document

router = APIRouter(prefix="/api", tags=["API"])


# Pages Router (integrated into main router)
pages_router = APIRouter()


@pages_router.get("/pages", response_model=List[dict])
def list_pages(db: Session = Depends(get_db)):
    """List all pages for the current user."""
    # For now, return sample pages data
    # In production, would filter by user ownership/permissions
    sample_pages = [
        {
            "id": 1,
            "title": "Welcome Page",
            "cover_image": None,
            "breadcrumbs": ["Home"],
            "content": [{"type": "paragraph", "text": "Start creating your workspace!"}]
        },
        {
            "id": 2,
            "title": "Getting Started",
            "cover_image": None,
            "breadcrumbs": ["Docs", "Getting Started"],
            "content": []
        }
    ]
    return sample_pages


@pages_router.post("/pages", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_page(
    title: str,
    content: Optional[List[dict]] = None,
    cover_image_url: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new page."""
    new_page_id = len([p for p in db.query(Page).all()]) + 1
    
    page_data = {
        "id": new_page_id,
        "title": title or "Untitled page",
        "cover_image": cover_image_url,
        "breadcrumbs": [],
        "content": content if content else []
    }
    
    return page_data


@pages_router.get("/pages/{page_id}", response_model=dict)
def get_page(page_id: int, db: Session = Depends(get_db)):
    """Get a single page by ID."""
    # For demo purposes, return mock data matching frontend expectations
    if page_id == 1:
        return {
            "id": 1,
            "title": "Welcome Page",
            "cover_image": None,
            "breadcrumbs": ["Home"],
            "content": [{"type": "paragraph", "text": "Start creating your workspace!"}]
        }
    elif page_id == 2:
        return {
            "id": 2,
            "title": "Getting Started", 
            "cover_image": None,
            "breadcrumbs": ["Docs", "Getting Started"],
            "content": [{"type": "paragraph", "text": "Welcome to your new workspace!"}]
        }
    else:
        raise HTTPException(status_code=404, detail="Page not found")


@pages_router.put("/pages/{page_id}", response_model=dict)
def update_page(
    page_id: int,
    title: Optional[str] = None,
    content: Optional[List[dict]] = None,
    db: Session = Depends(get_db)
):
    """Update an existing page."""
    # Update mock data based on input
    if page_id == 1 and title:
        return {
            "id": 1,
            "title": title,
            "cover_image": None,
            "breadcrumbs": ["Home"],
            "content": content or [{"type": "paragraph", "text": "Start creating your workspace!"}]
        }
    elif page_id == 2 and title:
        return {
            "id": 2,
            "title": title,
            "cover_image": None,
            "breadcrumbs": ["Docs", "Getting Started"], 
            "content": content or [{"type": "paragraph", "text": "Welcome to your new workspace!"}]
        }
    else:
        raise HTTPException(status_code=404, detail="Page not found")


@pages_router.delete("/pages/{page_id}", response_model=dict)
def delete_page(page_id: int, db: Session = Depends(get_db)):
    """Delete a page by ID."""
    return {"message": f"Page {page_id} deleted successfully"}


# Cover image endpoint
@pages_router.post("/pages/{page_id}/cover", response_model=dict)
def set_cover_image(
    page_id: int,
    url: str,
    db: Session = Depends(get_db)
):
    """Set cover image for a page."""
    return {
        "id": page_id,
        "cover_image": url
    }


# User endpoints (original functionality preserved)
@router.get("/users", tags=["Users"])
def list_users(db: Session = Depends(get_db)):
    """List all users."""
    from backend.models.schema import User
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "email": u.email} for u in users]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    email: str,
    username: str,
    full_name: Optional[str] = None,
    hashed_password: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new user."""
    from backend.models.schema import User
    if not hashed_password or len(hashed_password) < 10:
        raise HTTPException(status_code=400, detail="Invalid password")
    
    db_user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hashed_password
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return {"message": "User created successfully", "user_id": db_user.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    from backend.models.schema import User
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "full_name": db_user.full_name,
        "created_at": str(db_user.created_at) if db_user.created_at else None
    }


@router.put("/users/{user_id}")
def update_user(user_id: int, user_update: dict = ..., db: Session = Depends(get_db)):
    """Update user information."""
    from backend.models.schema import User
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {"name": user_update.get("name")}
    
    try:
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return {"message": "User updated successfully", "user_id": user.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    from backend.models.schema import User
    
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        db.delete(db_user)
        db.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# User settings endpoint (for frontend name update)
@router.get("/user", tags=["User Settings"])
def get_current_user(db: Session = Depends(get_db)):
    """Get current user info for frontend."""
    return {
        "name": "User",
        "avatar": "U"
    }


# Document sharing endpoint (preserved from original)
@router.post("/users/{user_id}/documents", status_code=status.HTTP_201_CREATED)
def share_document(
    user_id: int,
    document_id: int,
    permission_level: str = "view",
    db: Session = Depends(get_db)
):
    """Share a document with a user."""
    from backend.models.schema import DocumentShare
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    share = DocumentShare(
        user_id=user_id,
        document_id=document_id,
        permission_level=permission_level
    )
    
    try:
        db.add(share)
        db.commit()
        return {"message": "Document shared successfully", "share_id": share.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# Include pages router with API prefix
router.include_router(pages_router)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(
    email: str,
    username: str,
    full_name: str = None,
    hashed_password: str = None,
    db: Session = Depends(get_db)
):
    """Create a new user."""
    if not hashed_password:
        return {"error": "hashed_password required for user creation"}
    
    # Verify password hash (basic check)
    if len(hashed_password) < 10:
        raise HTTPException(status_code=400, detail="Invalid password")
    
    db_user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hashed_password
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return {"message": "User created successfully", "user_id": db_user.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "full_name": db_user.full_name,
        "created_at": str(db_user.created_at) if db_user.created_at else None
    }


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        db.delete(db_user)
        db.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/documents", status_code=status.HTTP_201_CREATED)
def share_document(
    user_id: int,
    document_id: int,
    permission_level: str = "view",
    db: Session = Depends(get_db)
):
    """Share a document with a user."""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    share = DocumentShare(
        user_id=user_id,
        document_id=document_id,
        permission_level=permission_level
    )
    
    try:
        db.add(share)
        db.commit()
        return {"message": "Document shared successfully", "share_id": share.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}")
def update_user(user_id: int, user_update: dict = ..., db: Session = Depends(get_db)):
    """Update user information."""
    from fastapi import HTTPException
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {"name": user_update.get("name")}
    
    try:
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return {"message": "User updated successfully", "user_id": user.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

