"""
Main FastAPI Application for Notion-like Web Application.
Entry point with authentication, CORS, and API router configuration. """
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import routers from endpoints (direct imports - will fail if files are missing)
try:
    from api.v1.endpoints.pages import pages_router  # noqa: F401
except ImportError as e:
    print(f"Warning: Could not import pages router: {e}")
    pass  # Will be created by the project setup script

try:
    from api.v1.endpoints.blocks import blocks_router  # noqa: F401
except ImportError as e:
    print(f"Warning: Could not import blocks router: {e}")
    pass

try:
    from api.v1.endpoints.workspaces import workspaces_router  # noqa: F401
except ImportError as e:
    print(f"Warning: Could not import workspaces router: {e}")
    pass

try:
    from api.v1.endpoints.search import search_router  # noqa: F401
except ImportError as e:
    print(f"Warning: Could not import search router: {e}")
    pass

# Import auth and config for middleware setup
from app.config import get_settings, Settings
from app.auth import token_manager

settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="A Notion-like web application with block-based rich text editing.",
)

# Configure CORS middleware to allow frontend requests
origins = settings.CORS_ORIGINS if hasattr(settings, 'CORS_ORIGINS') else [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"]
)

# Register API v1 routers with FastAPI (only if they exist and imported successfully)
if 'pages_router' in locals():
    app.include_router(pages_router, prefix="/api/v1")
if 'blocks_router' in locals():
    app.include_router(blocks_router, prefix="/api/v1")
if 'workspaces_router' in locals():
    app.include_router(workspaces_router, prefix="/api/v1")
if 'search_router' in locals():
    app.include_router(search_router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    
    Returns:
        Simple JSON response indicating service is healthy
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "1.0.0"
    }

# Root endpoint with API documentation links
@app.get("/")
def root():
    """
    Welcome and API information.
    
    Returns:
        JSON response with service info and API documentation links
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/health"
    }
