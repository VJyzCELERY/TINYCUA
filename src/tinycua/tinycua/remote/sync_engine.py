"""Sync engine for TinyCUA remote synchronization."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import httpx

from tinycua.exceptions import StorageError

try:
    import platformdirs
    HAS_PLATFORMDIRS = True
except ImportError:
    HAS_PLATFORMDIRS = False

if TYPE_CHECKING:
    from tinycua.remote.connection_manager import RemoteConnectionManager
    from tinycua.clients.backend import BackendClient

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    items_synced: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class QueuedOperation:
    """Represents a queued operation for offline sync."""

    operation_type: str
    session_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OfflineQueue:
    """Queue for storing operations when offline with persistence."""

    def __init__(self, queue_file: Optional[Path] = None) -> None:
        """Initialize OfflineQueue.

        Args:
            queue_file: Optional path for queue file. If None, uses default location.
        """
        if queue_file is not None:
            self._queue_file = queue_file
        elif HAS_PLATFORMDIRS:
            self._queue_file = Path(platformdirs.user_data_dir('tinycua')) / 'offline_queue.json'
        else:
            self._queue_file = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'tinycua' / 'offline_queue.json'
        self._queue: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load queue from persistent storage.

        Note: Uses blocking I/O for simplicity. For high-frequency operations,
        consider using aiofiles for async file operations.
        """
        if self._queue_file.exists():
            try:
                with open(self._queue_file, "r") as f:
                    self._queue = json.load(f)
                logger.debug("Loaded %s operations from persistent queue", len(self._queue))
            except (OSError, ValueError, TypeError) as e:
                logger.warning("Failed to load offline queue: %s", e)
                self._queue = []

    def _save(self) -> None:
        """Save queue to persistent storage.

        Note: Uses blocking I/O for simplicity. For high-frequency operations,
        consider using aiofiles for async file operations.
        """
        try:
            self._queue_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._queue_file, "w") as f:
                json.dump(self._queue, f)
        except (OSError, ValueError, TypeError) as e:
            logger.warning("Failed to save offline queue: %s", e)

    def enqueue(self, operation: dict[str, Any]) -> None:
        """Add an operation to the queue.

        Args:
            operation: Dictionary containing operation details.
        """
        self._queue.append(operation)
        self._save()
        logger.debug("Enqueued operation, queue size: %s", len(self._queue))

    def dequeue(self) -> dict[str, Any] | None:
        """Remove and return the oldest operation from the queue.

        Returns:
            The oldest operation dict, or None if queue is empty.
        """
        if self._queue:
            op = self._queue.pop(0)
            self._save()
            logger.debug("Dequeued operation, queue size: %s", len(self._queue))
            return op
        return None

    def clear(self) -> None:
        """Remove all operations from the queue."""
        self._queue.clear()
        self._save()

    def size(self) -> int:
        """Get the number of operations in the queue.

        Returns:
            Queue size.
        """
        return len(self._queue)

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if queue is empty, False otherwise.
        """
        return len(self._queue) == 0


class ConflictResolver:
    """Handles conflict resolution using last-write-wins strategy."""

    @staticmethod
    def resolve(local_item: dict[str, Any], remote_item: dict[str, Any]) -> dict[str, Any]:
        """Resolve conflict using last-write-wins.

        Args:
            local_item: Local item to compare
            remote_item: Remote item to compare

        Returns:
            The item with the most recent timestamp.
        """
        if not local_item:
            return remote_item
        if not remote_item:
            return local_item

        local_time = ConflictResolver._get_timestamp(local_item)
        remote_time = ConflictResolver._get_timestamp(remote_item)

        if local_time is None and remote_time is None:
            return local_item
        if local_time is None:
            return remote_item
        if remote_time is None:
            return local_item

        return local_item if local_time > remote_time else remote_item

    @staticmethod
    def _get_timestamp(item: dict[str, Any]) -> datetime | None:
        """Extract timestamp from item.

        Args:
            item: Item dictionary

        Returns:
            Datetime object or None if not found.
        """
        for key in ("updated_at", "created_at", "timestamp"):
            ts = item.get(key)
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except (ValueError, TypeError):
                    continue
        return None


class SyncEngine:
    """Engine for synchronizing data with remote Backend.

    Handles session and message sync, push/pull operations,
    and conflict resolution using last-write-wins strategy.
    """

    def __init__(
        self,
        connection_manager: RemoteConnectionManager,
    ) -> None:
        """Initialize SyncEngine.

        Args:
            connection_manager: RemoteConnectionManager instance
        """
        self._connection_manager = connection_manager
        self._last_sync: Optional[datetime] = None
        self._offline_queue = OfflineQueue()

    @property
    def last_sync(self) -> Optional[datetime]:
        """Get last sync timestamp.

        Returns:
            Datetime of last sync or None.
        """
        return self._last_sync

    async def sync_sessions(self) -> SyncResult:
        """Sync sessions to/from remote backend.

        Returns:
            SyncResult with sync status and count.
        """
        client = self._connection_manager.get_client()
        if not client or not self._connection_manager.is_connected:
            self._offline_queue.enqueue({"type": "sync_sessions"})
            return SyncResult(success=False, errors=["Not connected to remote - operation queued"])

        try:
            local_sessions = await self._get_local_sessions()
            remote_sessions = await client.list_sessions()

            merged = self._merge_sessions(local_sessions, remote_sessions)
            synced_count = 0
            errors = []

            for session in merged:
                try:
                    session_id = session.get("id")
                    session_name = session.get("name")
                    if session_id:
                        await client.update_session(session_id, session_name)
                    else:
                        await client.create_session(agent_id="default", name=session_name)
                    synced_count += 1
                except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
                    errors.append(f"Failed to push session: {e}")

            from tinycua.storage import LocalStorageManager
            storage_manager = LocalStorageManager.get_instance()
            if storage_manager is None:
                return SyncResult(success=False, errors=["Storage manager not available"])
            store = storage_manager.get_store()
            if store is None:
                return SyncResult(success=False, errors=["Storage not available"])

            local_ids = {s["id"] for s in local_sessions}
            for session in merged:
                if session["id"] not in local_ids:
                    try:
                        store.create_session(
                            name=session.get("name"),
                            session_id=uuid.UUID(session["id"]),
                        )
                    except (OSError, ValueError, TypeError) as e:
                        errors.append(f"Failed to save session locally: {e}")

            self._last_sync = datetime.now(timezone.utc)
            self._connection_manager.update_last_sync(self._last_sync.isoformat())

            logger.info("Synced %s sessions", synced_count)
            return SyncResult(success=len(errors) == 0, items_synced=synced_count, errors=errors)

        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            logger.exception("Session sync failed: %s: %s", type(e).__name__, e)
            return SyncResult(success=False, errors=[f"Session sync failed: {e}"])

    async def sync_messages(self, session_id: str) -> SyncResult:
        """Sync messages for a session.

        Args:
            session_id: ID of the session to sync

        Returns:
            SyncResult with sync status and count.
        """
        client = self._connection_manager.get_client()
        if not client or not self._connection_manager.is_connected:
            self._offline_queue.enqueue({"type": "sync_messages", "session_id": session_id})
            return SyncResult(success=False, errors=["Not connected to remote - operation queued"])

        try:
            remote_messages = await client.get_messages(session_id)
            local_messages = await self._get_local_messages(session_id)

            merged_messages, synced_count = self._merge_messages(local_messages, remote_messages)

            from tinycua.storage import LocalStorageManager
            storage_manager = LocalStorageManager.get_instance()
            errors = []
            if storage_manager:
                store = storage_manager.get_store()
                if store:
                    try:
                        session_uuid = uuid.UUID(session_id)
                        for msg in merged_messages:
                            store.add_message(
                                session_id=session_uuid,
                                role=msg.get("role", "user"),
                                content=msg.get("content", ""),
                                turn_index=msg.get("turn_index", 0),
                            )
                    except (OSError, ValueError, TypeError) as e:
                        errors.append(f"Failed to save messages locally: {e}")

            for msg in merged_messages:
                try:
                    await client.add_message(
                        session_id=session_id,
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                    )
                except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
                    errors.append(f"Failed to push message to remote: {e}")

            logger.info("Synced %s messages for session %s", synced_count, session_id)
            return SyncResult(success=len(errors) == 0, items_synced=synced_count, errors=errors)

        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            logger.exception("Message sync failed: %s: %s", type(e).__name__, e)
            return SyncResult(success=False, errors=[f"Message sync failed: {e}"])

    async def sync_memory(self) -> SyncResult:
        """Sync memory to remote backend.

        Returns:
            SyncResult with sync status and count.
        """
        client = self._connection_manager.get_client()
        if not client or not self._connection_manager.is_connected:
            self._offline_queue.enqueue({"type": "sync_memory"})
            return SyncResult(
                success=False,
                errors=["Not connected to remote - operation queued"]
            )

        try:
            local_sessions = await self._get_local_sessions()
            total_synced = 0
            errors = []

            for session in local_sessions:
                session_id = session.get("id")
                if not session_id:
                    continue

                try:
                    remote_memory = await client.get_memory(session_id)
                    local_memory = await self._get_local_memory(session_id)

                    merged_memory = self._merge_memory(local_memory, remote_memory)

                    if merged_memory:
                        await client.save_memory(session_id, merged_memory)
                        total_synced += 1
                except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
                    errors.append(f"Failed to sync memory for session {session_id}: {e}")

            self._last_sync = datetime.now(timezone.utc)
            self._connection_manager.update_last_sync(self._last_sync.isoformat())

            logger.info("Synced memory for %s sessions", total_synced)
            return SyncResult(success=len(errors) == 0, items_synced=total_synced, errors=errors)

        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            logger.exception("Memory sync failed: %s: %s", type(e).__name__, e)
            return SyncResult(success=False, errors=["Memory sync failed"])

    async def replay_offline_queue(self) -> SyncResult:
        """Replay queued operations after reconnection.

        Returns:
            SyncResult with replay status and count.
        """
        if not self._connection_manager.is_connected:
            return SyncResult(success=False, errors=["Not connected to remote"])

        total_processed = 0
        errors = []

        while not self._offline_queue.is_empty():
            operation = self._offline_queue.dequeue()
            if operation is None:
                break

            op_type = operation.get("type")
            try:
                if op_type == "sync_memory":
                    result = await self.sync_memory()
                    if result.success:
                        total_processed += 1
                    else:
                        errors.extend(result.errors)
                elif op_type == "sync_sessions":
                    result = await self.sync_sessions()
                    if result.success:
                        total_processed += 1
                    else:
                        errors.extend(result.errors)
                elif op_type == "sync_messages":
                    session_id = operation.get("session_id")
                    if session_id:
                        result = await self.sync_messages(session_id)
                        if result.success:
                            total_processed += 1
                        else:
                            errors.extend(result.errors)
            except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
                errors.append(f"Failed to replay {op_type}: {e}")

        logger.info("Replayed %s queued operations", total_processed)
        return SyncResult(
            success=len(errors) == 0,
            items_synced=total_processed,
            errors=errors if errors else []
        )

    async def push_all(self) -> SyncResult:
        """Push all local data to remote backend.

        Returns:
            SyncResult with push status and count.
        """
        client = self._connection_manager.get_client()
        if not client or not self._connection_manager.is_connected:
            return SyncResult(success=False, errors=["Not connected to remote"])

        try:
            total_synced = 0
            errors = []
            local_sessions = await self._get_local_sessions()

            for session in local_sessions:
                result = await self._push_session(client, session)
                if result.success:
                    total_synced += 1
                else:
                    errors.extend(result.errors)

            self._last_sync = datetime.now(timezone.utc)
            self._connection_manager.update_last_sync(self._last_sync.isoformat())
            logger.info("Pushed %s sessions to remote", total_synced)
            return SyncResult(
                success=len(errors) == 0,
                items_synced=total_synced,
                errors=errors if errors else []
            )

        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            logger.exception("Push failed: %s: %s", type(e).__name__, e)
            return SyncResult(success=False, errors=["Push failed"])

    async def pull_all(self) -> SyncResult:
        """Pull all remote data to local storage.

        Returns:
            SyncResult with pull status and count.
        """
        client = self._connection_manager.get_client()
        if not client or not self._connection_manager.is_connected:
            return SyncResult(success=False, errors=["Not connected to remote"])

        try:
            remote_sessions = await client.list_sessions()
            total_synced = 0
            errors = []

            for session in remote_sessions:
                result = await self._pull_session(session)
                if result.success:
                    total_synced += 1
                else:
                    errors.extend(result.errors)

            self._last_sync = datetime.now(timezone.utc)
            self._connection_manager.update_last_sync(self._last_sync.isoformat())
            logger.info("Pulled %s sessions from remote", total_synced)
            return SyncResult(
                success=len(errors) == 0,
                items_synced=total_synced,
                errors=errors if errors else []
            )

        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            logger.exception("Pull failed: %s: %s", type(e).__name__, e)
            return SyncResult(success=False, errors=["Pull failed"])

    def _get_from_store(self, method_name: str, *args, default=None):
        """Generic helper to call a method on LocalStorageManager's current store."""
        try:
            from tinycua.storage.local_storage import LocalStorageManager
            manager = LocalStorageManager()
            store = manager.get_store()
            if store is None:
                return default
            method = getattr(store, method_name, None)
            if method is None:
                return default
            return method(*args)
        except (StorageError, OSError, AttributeError):
            return default

    async def _get_local_sessions(self) -> list[dict[str, Any]]:
        """Get local sessions for sync.

        Returns:
            List of session dictionaries.
        """
        sessions = self._get_from_store("list_sessions", default=[])
        if not sessions:
            return []
        return [
            {
                "id": str(s.id),
                "name": s.name,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]

    async def _get_local_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get local messages for a session.

        Args:
            session_id: Session ID

        Returns:
            List of message dictionaries.
        """
        try:
            messages = self._get_from_store("get_messages", uuid.UUID(session_id), default=[])
        except ValueError:
            return []
        if not messages:
            return []
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "turn_index": m.turn_index,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    async def _get_local_memory(self, session_id: str) -> dict[str, Any]:
        """Get local memory for a session.

        Args:
            session_id: Session ID

        Returns:
            Memory dictionary.
        """
        try:
            memory = self._get_from_store("get_memory", uuid.UUID(session_id), default=None)
        except ValueError:
            return {}
        if memory is None:
            return {}
        return {"content": memory.content, "updated_at": memory.updated_at.isoformat() if memory.updated_at else None}

    def _merge_memory(
        self,
        local_memory: dict[str, Any],
        remote_memory: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge memory using last-write-wins strategy.

        Args:
            local_memory: Local memory data
            remote_memory: Remote memory data

        Returns:
            Merged memory dictionary.
        """
        return ConflictResolver.resolve(local_memory, remote_memory)

    def _merge_sessions(
        self,
        local_sessions: list[dict[str, Any]],
        remote_sessions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge sessions using last-write-wins strategy.

        Args:
            local_sessions: Local session data
            remote_sessions: Remote session data

        Returns:
            List of merged sessions.
        """
        merged: dict[str, dict[str, Any]] = {}
        for session in local_sessions + remote_sessions:
            session_id = session.get("id")
            if not session_id:
                continue

            existing = merged.get(session_id)
            if existing is None:
                merged[session_id] = session
            else:
                resolved = ConflictResolver.resolve(session, existing)
                merged[session_id] = resolved

        return list(merged.values())

    def _merge_messages(
        self,
        local_messages: list[dict[str, Any]],
        remote_messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        """Merge messages using last-write-wins strategy.

        Args:
            local_messages: Local message data
            remote_messages: Remote message data

        Returns:
            Tuple of (merged messages list, count).
        """
        merged: dict[str, dict[str, Any]] = {}
        for msg in local_messages + remote_messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            existing = merged.get(msg_id)
            if existing is None:
                merged[msg_id] = msg
            else:
                resolved = ConflictResolver.resolve(msg, existing)
                merged[msg_id] = resolved

        return list(merged.values()), len(merged)

    async def _push_session(
        self, client: "BackendClient", session: dict[str, Any]
    ) -> SyncResult:
        """Push a session to remote backend.

        Args:
            client: BackendClient instance
            session: Session data to push

        Returns:
            SyncResult indicating success or failure.
        """
        try:
            session_id = session.get("id")
            session_name = session.get("name", "session")
            if session_id:
                await client.update_session(session_id, session_name)
            else:
                await client.create_session(agent_id="default", name=session_name)
            return SyncResult(success=True, items_synced=1)
        except (ConnectionError, OSError, ValueError, httpx.HTTPStatusError) as e:
            error_msg = f"Failed to push session {session.get('id')}: {e}"
            logger.exception(error_msg)
            return SyncResult(success=False, errors=[error_msg])

    async def _pull_session(self, session: dict[str, Any]) -> SyncResult:
        """Pull a session from remote to local storage.

        Args:
            session: Session data from remote

        Returns:
            SyncResult indicating success or failure.
        """
        try:
            from tinycua.storage import LocalStorageManager

            storage_manager = LocalStorageManager.get_instance()
            if storage_manager is None:
                return SyncResult(success=False, errors=["Storage manager not available"])
            store = storage_manager.get_store()
            if store:
                session_id = session.get("id")
                if session_id:
                    try:
                        session_uuid = uuid.UUID(session_id)
                    except ValueError:
                        session_uuid = uuid.uuid4()
                else:
                    session_uuid = uuid.uuid4()
                store.create_session(
                    name=session.get("name", "remote_session"),
                    session_id=session_uuid,
                )
            return SyncResult(success=True, items_synced=1)
        except (OSError, ValueError, TypeError) as e:
            error_msg = f"Failed to pull session {session.get('id')}: {e}"
            logger.exception(error_msg)
            return SyncResult(success=False, errors=[error_msg])


__all__ = ["SyncEngine", "SyncResult", "OfflineQueue", "QueuedOperation", "ConflictResolver"]
