"""Run API routes."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from tinycua_runner.auth import validate_runner_token
from tinycua_runner.executor import Executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/v1", tags=["run"])
security = HTTPBearer(auto_error=False)


class RunRequest(BaseModel):
    """Request model for running an agent."""

    agent_config: dict[str, Any]
    session_id: str
    db_url: str
    user_input: str
    tools: list[dict[str, Any]] | None = None
    messages: list[dict[str, Any]] | None = None


async def get_current_runner(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> bool:
    """Validate runner token."""
    return await validate_runner_token(credentials)


def format_sse_event(event: Any) -> str:
    """Format an event as SSE data."""
    if isinstance(event, dict):
        return f"data: {json.dumps(event)}\n\n"
    elif hasattr(event, "model_dump"):
        return f"data: {json.dumps(event.model_dump())}\n\n"
    elif hasattr(event, "model_dump_json"):
        return f"data: {event.model_dump_json()}\n\n"
    else:
        return f"data: {str(event)}\n\n"


@router.post("/run")
async def run_agent(
    request: RunRequest,
    _: bool = Depends(get_current_runner),
) -> StreamingResponse:
    """Execute an agent with session context.

    Args:
        request: The run request
        _: Validated runner token

    Returns:
        Streaming response with SSE events
    """
    executor = Executor(
        db_url=request.db_url,
        session_id=request.session_id,
        bundled_tools=request.tools,
    )

    async def event_generator():
        try:
            async for event in executor.execute(
                agent_config=request.agent_config,
                user_input=request.user_input,
                messages=request.messages,
            ):
                yield format_sse_event(event)
        except Exception as e:
            logger.error(f"Execution error: {e}")
            yield f"data: {{'error': '{str(e)}'}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
