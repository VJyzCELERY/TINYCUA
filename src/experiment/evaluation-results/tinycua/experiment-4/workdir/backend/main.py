"""FastAPI Application entry point for Notion-like app."""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.api.database import engine, init_db, get_db
from backend.models.schema import Base
from backend.api.routers import users, pages

app = FastAPI(
    title="Notion-like App API",
    description="Backend API for a Notion-style workspace application",
    version="1.0.0"
)

# Add CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router, prefix="/api")
app.include_router(pages.pages_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "message": "Notion-like App API",
        "docs_url": "/docs"
    }


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    print("Database initialized successfully.")


# Mount static files for frontend (if needed)
# app.mount("/static", StaticFiles(directory="frontend"), name="static")
