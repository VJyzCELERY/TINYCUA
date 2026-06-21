"""API routers module."""
from backend.api.auth import router as auth_router
from backend.api.routers import users, pages

__all__ = [
    "auth_router", 
    "users", 
    "pages",
]
