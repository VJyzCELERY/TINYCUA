"""Main FastAPI application for tinycua-backend."""

import logging
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI

from tinycua_backend.config import init_config, get_config
from tinycua_backend.database import create_tables
from tinycua_backend.guest import get_guest_session_store
from tinycua_backend.routers import agents, sessions, run, tools
from tinycua_backend.routers.auth import router as auth_router
from tinycua_backend.routers.guest import router as guest_router
from tinycua_sdk.storage import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting tinycua-backend...")

    # Initialize config - look for config.yaml in the same directory as main.py
    config_dir = Path(__file__).parent.parent
    config_path = config_dir / "config.yaml"
    logger.info(f"Loading config from: {config_path}")
    logger.info(f"Config exists: {config_path.exists()}")
    init_config(str(config_path))
    config = get_config()
    logger.info(f"Config loaded: {config.database.url}")

    # Create tables
    create_tables()
    logger.info("Database tables created")

    # Create SDK tables (sessions, messages) via SessionStore
    SessionStore(config.database.url).create_tables()
    logger.info("SDK tables (sessions, messages) created")

    # Start guest session cleanup task
    store = get_guest_session_store()
    await store.start_cleanup_task()
    logger.info("Guest session store started")

    yield

    # Stop guest session cleanup
    store.stop_cleanup_task()
    logger.info("Guest session store stopped")

    logger.info("Shutting down tinycua-backend...")


app = FastAPI(
    title="tinycua-backend",
    description="Backend API for agent deployment and management",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth_router)
app.include_router(guest_router)
app.include_router(agents.router)
app.include_router(sessions.router)
app.include_router(run.router)
app.include_router(tools.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from tinycua_backend.config import get_config

    config = get_config()
    uvicorn.run(app, host=config.server.host, port=config.server.port)
