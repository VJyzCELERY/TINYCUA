"""Main FastAPI application for tinycua-backend."""

import logging
import os
from pathlib import Path

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tinycua_backend.config import init_config, get_config
from tinycua_backend.storage.database import create_tables
from tinycua_backend.storage.search_sqlite import SQLiteSearch
# TenantMiddleware removed: endpoints rely on Depends(get_current_tenant)
# which supports all auth methods (Bearer, API key, global key)
from tinycua_backend.api import sessions
from tinycua_backend.api.auth import router as auth_router
from tinycua_backend.api.messages import router as messages_router
from tinycua_backend.api.tenant import router as tenant_router
from tinycua_backend.sync.endpoints import router as sync_router

# NOTE: SessionStore is imported from tinycua_sdk for storage-only purposes.
# The backend does not use any execution logic from the SDK (agent loops,
# tools, memory management, etc.). This import is strictly for creating and
# managing the session/message database tables via the SDK's storage layer.
from tinycua_sdk.storage.store import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read CORS origins from environment variable at module level before app creation.
_cors_origins_env = os.environ.get("TINYCUA_CORS_ORIGINS", "")
_cors_origins: list[str] = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else []
)
if "*" in _cors_origins:
    raise ValueError(
        "Cannot use origins='*' with allow_credentials=True. "
        "Specify explicit origins or disable credentials."
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting tinycua-backend...")

    # Initialize config - look for config.yaml in the same directory as main.py
    config_dir = Path(__file__).parent.parent
    config_path = config_dir / "config.yaml"
    logger.info("Loading config from: %s", config_path)
    logger.info("Config exists: %s", config_path.exists())
    init_config(str(config_path))
    config = get_config()
    logger.info("Config loaded successfully")

    # Create tables
    create_tables()
    logger.info("Database tables created")

    # Create SDK tables (sessions, messages) via SessionStore
    SessionStore(config.database.url).create_tables()
    logger.info("SDK tables (sessions, messages) created")

    # Initialize FTS search for SQLite
    if config.database.url.startswith("sqlite"):
        search = SQLiteSearch()
        search.initialize(SessionStore(config.database.url).engine)
        logger.info("FTS search initialized")

    yield

    logger.info("Shutting down tinycua-backend...")


app = FastAPI(
    title="tinycua-backend",
    description="Backend API for session storage and management",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS at app creation time with runtime values from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(sessions.router)
app.include_router(messages_router)
app.include_router(tenant_router)
app.include_router(sync_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from tinycua_backend.config import init_config, get_config

    config_dir = Path(__file__).parent.parent
    config_path = config_dir / "config.yaml"
    init_config(str(config_path))
    config = get_config()
    uvicorn.run(app, host=config.server.host, port=config.server.port)
