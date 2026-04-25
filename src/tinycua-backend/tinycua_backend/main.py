"""Main FastAPI application for tinycua-backend."""

import logging
from pathlib import Path

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tinycua_backend.config import init_config, get_config
from tinycua_backend.storage.database import create_tables
from tinycua_backend.tenant.middleware import TenantMiddleware
from tinycua_backend.api import sessions
from tinycua_backend.api.auth import router as auth_router
from tinycua_backend.api.messages import router as messages_router
from tinycua_backend.api.tenant import router as tenant_router

# NOTE: SessionStore is imported from tinycua_sdk for storage-only purposes.
# The backend does not use any execution logic from the SDK (agent loops,
# tools, memory management, etc.). This import is strictly for creating and
# managing the session/message database tables via the SDK's storage layer.
from tinycua_sdk.storage.store import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting tinycua-backend...")

    # Initialize config - look for config.yaml in the same directory as main.py
    config_dir = Path(__file__).parent.parent
    config_path = config_dir / "config.yaml"
    logger.info(f"Loading config from: {config_path}")
    logger.info(f"Config exists: {config_path.exists()}")
    init_config(str(config_path))
    config = get_config()
    logger.info("Config loaded successfully")

    # Create tables
    create_tables()
    logger.info("Database tables created")

    # Create SDK tables (sessions, messages) via SessionStore
    SessionStore(config.database.url).create_tables()
    logger.info("SDK tables (sessions, messages) created")

    yield

    logger.info("Shutting down tinycua-backend...")


app = FastAPI(
    title="tinycua-backend",
    description="Backend API for session storage and management",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TenantMiddleware)

# Include routers
app.include_router(auth_router)
app.include_router(sessions.router)
app.include_router(messages_router)
app.include_router(tenant_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from tinycua_backend.config import get_config

    config = get_config()
    uvicorn.run(app, host=config.server.host, port=config.server.port)
