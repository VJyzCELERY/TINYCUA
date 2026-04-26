"""Sync service for multi-device synchronization."""

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from tinycua_backend.config import get_config
from tinycua_backend.sync.resolver import detect_conflict, resolve_conflict

from tinycua_sdk.storage.store import SessionStore


class SyncService:
    """Service for synchronizing sessions and memory across devices."""

    def __init__(self) -> None:
        self._store: SessionStore | None = None
        self._store_lock = threading.Lock()

    def _get_store(self) -> SessionStore:
        """Get cached SessionStore instance."""
        config = get_config()
        if self._store is None or self._store.database_url != config.database.url:
            with self._store_lock:
                if self._store is None or self._store.database_url != config.database.url:
                    self._store = SessionStore(config.database.url)
        return self._store

    def sync_sessions(
        self,
        user_id: str,
        sessions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Sync sessions from client with last-write-wins resolution.

        Args:
            user_id: The user ID
            sessions: List of session dicts to sync

        Returns:
            Dict with synced sessions, conflicts, and errors
        """
        store = self._get_store()
        synced = []
        conflicts = []
        errors = []

        for session_data in sessions:
            try:
                session_id = session_data.get("id")
                if not session_id:
                    errors.append({"error": "Missing session ID", "data": session_data})
                    continue

                uuid_session_id = uuid.UUID(session_id)
                existing = store.get_session(uuid_session_id)

                if existing:
                    existing_dict = {
                        "id": str(existing.id),
                        "name": existing.name,
                        "user_id": str(existing.user_id),
                        "created_at": existing.created_at.isoformat(),
                        "updated_at": existing.updated_at.isoformat(),
                    }

                    if detect_conflict(session_data, existing_dict):
                        winner, resolution = resolve_conflict(session_data, existing_dict)
                        if resolution == "remote_wins":
                            store.update_session(
                                uuid_session_id,
                                name=winner.get("name"),
                            )
                            synced.append(winner)
                        else:
                            synced.append(existing_dict)
                        conflicts.append(
                            {
                                "session_id": session_id,
                                "resolution": resolution,
                            }
                        )
                    else:
                        synced.append(existing_dict)
                else:
                    new_session = store.create_session(
                        name=session_data.get("name", "Synced Session"),
                        user_id=user_id,
                        session_id=uuid_session_id,
                    )
                    synced.append(
                        {
                            "id": str(new_session.id),
                            "name": new_session.name,
                            "user_id": str(new_session.user_id),
                            "created_at": new_session.created_at.isoformat(),
                            "updated_at": new_session.updated_at.isoformat(),
                        }
                    )
            except Exception as e:
                errors.append({"error": str(e), "data": session_data})

        return {
            "synced": synced,
            "conflicts": conflicts,
            "errors": errors,
        }

    def sync_memory(
        self,
        user_id: str,
        memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Sync memory items from client.

        Args:
            user_id: The user ID
            memories: List of memory dicts to sync

        Returns:
            Dict with synced memories and errors
        """
        store = self._get_store()
        synced = []
        errors = []

        for memory_data in memories:
            try:
                session_id = memory_data.get("session_id")
                if not session_id:
                    errors.append({"error": "Missing session_id", "data": memory_data})
                    continue

                uuid_session_id = uuid.UUID(session_id)
                existing = store.get_session(uuid_session_id)

                if not existing:
                    errors.append({"error": "Session not found", "data": memory_data})
                    continue

                role = memory_data.get("role", "user")
                content = memory_data.get("content", "")
                reasoning = memory_data.get("reasoning")

                message = store.add_message(
                    session_id=uuid_session_id,
                    role=role,
                    content=content,
                    reasoning=reasoning,
                )

                if message:
                    synced.append(
                        {
                            "id": str(message.id),
                            "session_id": session_id,
                            "role": message.role,
                            "content": message.content,
                            "reasoning": message.reasoning,
                            "turn_index": message.turn_index,
                            "created_at": message.created_at.isoformat(),
                        }
                    )
            except Exception as e:
                errors.append({"error": str(e), "data": memory_data})

        return {"synced": synced, "errors": errors}

    def pull_updates(
        self,
        user_id: str,
        since: str | None = None,
    ) -> dict[str, Any]:
        """Pull updates since timestamp.

        Args:
            user_id: The user ID
            since: ISO timestamp to pull updates since

        Returns:
            Dict with sessions and memories updated since timestamp
        """
        store = self._get_store()
        sessions = store.list_sessions(user_id=user_id)

        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            sessions = [
                s
                for s in sessions
                if s.updated_at.replace(tzinfo=timezone.utc) > since_dt
            ]

        memories = []
        for session in sessions:
            messages = store.get_messages(session.id)
            for msg in messages:
                if since:
                    msg_created = msg.created_at.replace(tzinfo=timezone.utc)
                    if msg_created <= since_dt:
                        continue
                memories.append(
                    {
                        "id": str(msg.id),
                        "session_id": str(session.id),
                        "role": msg.role,
                        "content": msg.content,
                        "reasoning": msg.reasoning,
                        "turn_index": msg.turn_index,
                        "created_at": msg.created_at.isoformat(),
                    }
                )

        return {
            "sessions": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "user_id": str(s.user_id),
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in sessions
            ],
            "memories": memories,
        }
