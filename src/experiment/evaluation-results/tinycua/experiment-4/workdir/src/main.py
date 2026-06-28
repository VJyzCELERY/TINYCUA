from datetime import datetime, timedelta
from typing import Optional, List
from uuid import uuid4
import os
from dotenv import load_dotenv
from pathlib import Path
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

# Configure security settings - use environment variable or default
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Database connection setup - create engine locally to avoid circular imports
def get_database_path():
    """Get absolute database path from workspace root."""
    workspace_root = Path(__file__).resolve().parent.parent.parent
    env_url = os.getenv("DATABASE_URL")
    
    if not env_url or not env_url.startswith("sqlite"):
        return workspace_root / "app.db"
    
    path_str = env_url.replace("sqlite:///", "")
    
    if path_str.startswith("/"):
        return Path(path_str).resolve()
    else:
        db_path = workspace_root / path_str
        return db_path.resolve()


from src.config.init_db import init_database, create_engine

# Create engine at module load time for dependency injection
db_path = get_database_path()
engine = create_engine(db_path)


import sqlalchemy as sa
from fastapi import FastAPI, Request, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Session, select

# Create FastAPI app instance
app = FastAPI(
    title="Notion-like App API",
    description="Backend API for a Notion-like collaborative workspace application",
    version="0.1.0"
)

# CORS middleware configuration
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    """Add CORS headers to all responses."""
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    response = await call_next(request)
    
    for origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    
    return response

# Handle preflight requests for all routes
@app.options("*{path}")
async def handle_preflight(request: Request):
    """Handle CORS preflight OPTIONS requests."""
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    response = Response(status_code=204)
    for origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    # Database is initialized at module load time via engine = create_engine(db_path)
    # Just ensure tables exist for this session
    from src.config.init_db import init_database
    init_database()


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "service": "notion-like-app"}


# Version info endpoint
@app.get("/api/v1/version")
async def version_info():
    """Version information endpoint."""
    return {
        "version": "0.1.0",
        "service": "notion-like-app",
        "api_version": "v1"
    }


# =============================================================================
# Authentication Layer (JWT-based)
# =============================================================================

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Get the hash for a password."""
    return pwd_context.hash(password)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[dict]:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Return username in dict format for API use
    return {"username": username}


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> str:
    """Get current active user."""
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user["username"]


# =============================================================================
# Authentication Endpoints
# =============================================================================

@app.post("/api/v1/auth/login", response_model=dict)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint - returns JWT token."""
    
    # For now, accept any username/password (can be enhanced with user database later)
    username = form_data.username
    password = form_data.password
    
    if not username or not password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token (in production, validate against user database)
    expire = datetime.utcnow() + timedelta(minutes=30)  # Token expires in 30 minutes
    to_encode = {
        "sub": username,
        "exp": int(expire.timestamp())
    }
    
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username
    }


@app.get("/api/v1/auth/me", response_model=dict)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "username": current_user["username"],
        "authenticated": True
    }


@app.post("/api/v1/auth/logout")
async def logout(current_user: dict = Depends(get_current_user), response: Response = None):
    """Logout endpoint - token becomes invalid after expiration."""
    # In production, you could add a tokens table to blacklist tokens
    return {"message": "Successfully logged out"}


@app.get("/api/v1/auth/verify")
async def verify_token(token: str = Depends(oauth2_scheme)):
    """Verify if a JWT token is valid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"valid": True, "username": payload.get("sub")}
    except JWTError:
        return {"valid": False, "error": "Invalid or expired token"}


# =============================================================================
# Blocks API Endpoints (CRUD operations)
# =============================================================================

from src.schemas.blocks import BlockCreate, BlockUpdate, BlockResponse
from src.models.blocks import Block, Page, DocumentProperties


def get_db():
    """Dependency to provide SQLModel database session with proper transaction handling."""
    with Session(engine) as session:
        yield session


@app.post("/api/v1/blocks", response_model=BlockResponse)
async def create_block(block_data: BlockCreate, db_session: Session = Depends(get_db)):
    """
    Create a new block with Pydantic validation.
    
    Supports block types: text, code, heading, image, bullet-list
    
    - type: Required block type (default: "text")
    - content: Text content for text blocks only
    - parent_id: Nullable ID of parent block (for nested structure)
    """
    new_block = Block(
        id=block_data.id or str(uuid4()),  # Allow optional client-provided ID
        type=block_data.type,
        text_content=block_data.content,
        parent_id=block_data.parent_id
    )
    
    db_session.add(new_block)
    db_session.commit()
    db_session.refresh(new_block)
    
    return new_block


@app.get("/api/v1/blocks/{block_id}", response_model=BlockResponse)
async def get_block(block_id: str, db_session: Session = Depends(get_db)):
    """Retrieve a block by ID from database, returning full BlockResponse with type (text/code/heading/image/bullet-list) and text content."""
    block = db_session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block


@app.put("/api/v1/blocks/{block_id}/update", response_model=BlockResponse)
async def update_block(block_id: str, update_data: BlockUpdate, db_session: Session = Depends(get_db)):
    """Update an existing block's content or type."""
    block = db_session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    # Apply updates from validated Pydantic schema
    if update_data.type is not None:
        block.type = update_data.type
    if update_data.content is not None:
        block.text_content = update_data.content
    if update_data.title is not None and block.type == "heading":
        block.text_content = update_data.title
    
    db_session.add(block)
    db_session.commit()
    db_session.refresh(block)
    
    return block


@app.delete("/api/v1/blocks/{block_id}")
async def delete_block(block_id: str, db_session: Session = Depends(get_db)):
    """Delete a block by ID."""
    block = db_session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    db_session.delete(block)
    db_session.commit()
    
    return {"message": f"Block {block_id} deleted successfully"}


@app.get("/api/v1/search")
async def search(q: str = None, page: int = 1, page_size: int = 20, db_session: Session = Depends(get_db)):
    """
    Search endpoint with pagination.
    
    Search across blocks, pages, and document properties for the given query string.
    Supports fuzzy text matching in block content, titles, and property fields.
    
    Query Parameters:
        - q (query): Search term to match against (required)
        - page: Page number for pagination (default: 1)
        - page_size: Number of results per page (default: 20, max: 100)
        
    Returns paginated search results with metadata.
    """
    if not q or len(q.strip()) == 0:
        return {
            "query": "",
            "page": page,
            "page_size": page_size,
            "total_results": 0,
            "results": []
        }
    
    # Normalize query to lowercase for case-insensitive search
    normalized_query = q.lower().strip()
    
    # Calculate pagination offset
    offset = (page - 1) * page_size
    
    # Limit page_size to max 100
    effective_page_size = min(page_size, 100)
    
    with db_session as session:
        # Search blocks by content and type
        search_query_blocks = sa.or_(
            Block.text_content.ilike(f"%{normalized_query}%"),
            Block.type.ilike(normalized_query)
        )
        
        block_results = session.exec(select(Block).filter(search_query_blocks, Block.id.isnot(None)).limit(effective_page_size).offset(offset)).all()
        
        # Search pages by title (include all pages since parent_page_id is nullable)
        search_query_pages = sa.or_(
            Page.title.ilike(f"%{normalized_query}%")
        )
        
        page_results = session.exec(select(Page).filter(search_query_pages).limit(effective_page_size).offset(offset)).all()
        
        # Search document properties by title and other fields
        search_query_properties = sa.or_(
            DocumentProperties.title.ilike(f"%{normalized_query}%"),
            DocumentProperties.icon_url.isnot(None),
            DocumentProperties.cover_image_url.isnot(None)
        )
        
        property_results = session.exec(select(DocumentProperties).filter(search_query_properties).limit(effective_page_size).offset(offset)).all()
        
        # Count total matching results for pagination metadata using select(func.count())
        block_count_result = session.scalar(select(sa.func.count()).select_from(Block).where(search_query_blocks, Block.id.isnot(None)))
        page_count_result = session.scalar(select(sa.func.count()).select_from(Page).where(search_query_pages))
        property_count_result = session.scalar(select(sa.func.count()).select_from(DocumentProperties).where(search_query_properties))
        
        block_count = int(block_count_result) if block_count_result is not None else 0
        page_count = int(page_count_result) if page_count_result is not None else 0
        property_count = int(property_count_result) if property_count_result is not None else 0
        
        total_results = block_count + page_count + property_count
        
        # Format results with pagination metadata
        results = []
        
        for block in block_results:
            results.append({
                "type": "block",
                "id": str(block.id),
                "title": f"[{block.type}] Block",
                "content": (block.text_content or "")[:100] + ("..." if len(str(block.text_content or "")) > 100 else ""),
                "match_field": "content"
            })
        
        for page in page_results:
            results.append({
                "type": "page",
                "id": str(page.id),
                "title": (page.title or "")[:200] + ("..." if len(str(page.title)) > 200 else ""),
                "content": None,
                "match_field": "title"
            })
        
        for prop in property_results:
            results.append({
                "type": "property",
                "id": str(prop.id),
                "title": f"[{prop.title or ''}] {prop.icon_url or ''} {prop.cover_image_url or ''}",
                "content": None,
                "match_field": "title"
            })
        
        return {
            "query": q,
            "page": page,
            "page_size": effective_page_size,
            "total_results": total_results,
            "total_pages": (total_results + effective_page_size - 1) // effective_page_size if effective_page_size > 0 else 0,
            "results": results
        }

