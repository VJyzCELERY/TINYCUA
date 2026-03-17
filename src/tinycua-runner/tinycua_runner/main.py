"""Main FastAPI application for tinycua-runner."""

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI

from tinycua_runner.config import init_config
from tinycua_runner.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting tinycua-runner...")

    init_config("config.yaml")
    logger.info("Runner initialized")

    yield

    logger.info("Shutting down tinycua-runner...")


app = FastAPI(
    title="tinycua-runner",
    description="Runner service for agent execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/internal/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from tinycua_runner.config import get_config

    config = get_config()
    uvicorn.run(app, host=config.host, port=config.port)
