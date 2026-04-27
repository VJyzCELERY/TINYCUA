"""Sync API endpoints for multi-device synchronization."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tinycua_backend.auth.core import CurrentTenant, get_current_tenant
from tinycua_backend.sync.service import SyncService

router = APIRouter(prefix="/v1/sync", tags=["sync"])
_sync_service = SyncService()


class SessionSyncItem(BaseModel):
    """Session item for sync."""

    id: str
    name: str | None = None
    updated_at: str | None = None


class SessionSyncRequest(BaseModel):
    """Request model for session sync."""

    sessions: list[SessionSyncItem]


class SessionSyncResponse(BaseModel):
    """Response model for session sync."""

    synced: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class MemorySyncItem(BaseModel):
    """Memory item for sync."""

    id: str
    content: str | None = None
    updated_at: str | None = None


class MemorySyncRequest(BaseModel):
    """Request model for memory sync."""

    memories: list[MemorySyncItem]


class MemorySyncResponse(BaseModel):
    """Response model for memory sync."""

    synced: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class PullResponse(BaseModel):
    """Response model for pull updates."""

    sessions: list[dict[str, Any]]
    memories: list[dict[str, Any]]


@router.post("/sessions", response_model=SessionSyncResponse)
async def sync_sessions(
    sync_data: SessionSyncRequest,
    current: CurrentTenant = Depends(get_current_tenant),
) -> SessionSyncResponse:
    """Sync sessions from client with last-write-wins resolution.

    Args:
        sync_data: The session sync data
        current: The current tenant

    Returns:
        Synced sessions, conflicts, and errors
    """
    user_id = str(current.user_id) if current.user_id else str(current.tenant.id)

    sessions_dict = [s.model_dump() for s in sync_data.sessions]
    result = _sync_service.sync_sessions(user_id, sessions_dict)

    return SessionSyncResponse(**result)


@router.post("/memory", response_model=MemorySyncResponse)
async def sync_memory(
    sync_data: MemorySyncRequest,
    current: CurrentTenant = Depends(get_current_tenant),
) -> MemorySyncResponse:
    """Sync memory items from client.

    Args:
        sync_data: The memory sync data
        current: The current tenant

    Returns:
        Synced memories and errors
    """
    user_id = str(current.user_id) if current.user_id else str(current.tenant.id)

    memories_dict = [m.model_dump() for m in sync_data.memories]
    result = _sync_service.sync_memory(user_id, memories_dict)

    return MemorySyncResponse(**result)


@router.get("/pull", response_model=PullResponse)
async def pull_updates(
    current: CurrentTenant = Depends(get_current_tenant),
    since: str | None = None,
) -> PullResponse:
    """Pull updates since timestamp.

    Args:
        current: The current tenant
        since: ISO timestamp to pull updates since

    Returns:
        Sessions and memories updated since timestamp
    """
    user_id = str(current.user_id) if current.user_id else str(current.tenant.id)

    result = _sync_service.pull_updates(user_id, since)

    return PullResponse(**result)
