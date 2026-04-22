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
                logger.debug(f"Loaded {len(self._queue)} operations from persistent queue")
            except Exception as e:
                logger.warning(f"Failed to load offline queue: {e}")
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
        except Exception as e:
            logger.warning(f"Failed to save offline queue: {e}")

    def enqueue(self, operation: dict[str, Any]) -> None:
        """Add an operation to the queue.

        Args:
            operation: Dictionary containing operation details.
        """
        self._queue.append(operation)
        self._save()
        logger.debug(f"Enqueued operation, queue size: {len(self._queue)}")

    def dequeue(self) -> dict[str, Any] | None:
        """Remove and return the oldest operation from the queue.

        Returns:
            The oldest operation dict, or None if queue is empty.
        """
        if self._queue:
            op = self._queue.pop(0)
            self._save()
            logger.debug(f"Dequeued operation, queue size: {len(self._queue)}")
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
            remote_sessions = await client.list_agents()

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
                except Exception as e:
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
                            uuid.UUID(session["id"]),
                            name=session.get("name"),
                        )
                    except Exception as e:
                        errors.append(f"Failed to save session locally: {e}")

            self._last_sync = datetime.now(timezone.utc)
            self._connection_manager.update_last_sync(self._last_sync.isoformat())

            logger.info(f"Synced {synced_count} sessions")
            return SyncResult(success=len(errors) == 0, items_synced=synced_count, errors=errors)

        except Exception as e:
            logger.exception(f"Session sync failed: {type(e).__name__}: {e}")
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
                            store.create_message(
                                session_id=session_uuid,
                                role=msg.get("role", "user"),
                                content=msg.get("content", ""),
                                turn_index=msg.get("turn_index", 0),
                            )
                    except Exception as e:
                        errors.append(f"Failed to save messages locally: {e}")

            for msg in merged_messages:
                try:
                    await client.add_message(
                        session_id=session_id,
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                    )
                except Exception as e:
                    errors.append(f"Failed to push message to remote: {e}")

            logger.info(f"Synced {synced_count} messages for session {session_id}")
            return SyncResult(success=len(errors) == 0, items_synced=synced_count, errors=errors)

        except Exception as e:
            logger.exception(f"Message sync failed: {type(e).__name__}: {e}")
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
                except Exception as e:
                    errors.append(f"Failed to sync memory for session {session_id}: {e}")

            self._last_sync = datetime.now(timezone.utc)
            self._connection_manager.update_last_sync(self._last_sync.isoformat())

            logger.info(f"Synced memory for {total_synced} sessions")
            return SyncResult(success=len(errors) == 0, items_synced=total_synced, errors=errors)

        except Exception as e:
            logger.exception(f"Memory sync failed: {type(e).__name__}: {e}")
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
            except Exception as e:
                errors.append(f"Failed to replay {op_type}: {e}")

        logger.info(f"Replayed {total_processed} queued operations")
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
            logger.info(f"Pushed {total_synced} sessions to remote")
            return SyncResult(
                success=len(errors) == 0,
                items_synced=total_synced,
                errors=errors if errors else []
            )

        except Exception as e:
            logger.exception(f"Push failed: {type(e).__name__}: {e}")
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
            remote_sessions = await client.list_agents()
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
            logger.info(f"Pulled {total_synced} sessions from remote")
            return SyncResult(
                success=len(errors) == 0,
                items_synced=total_synced,
                errors=errors if errors else []
            )

        except Exception as e:
            logger.exception(f"Pull failed: {type(e).__name__}: {e}")
            return SyncResult(success=False, errors=["Pull failed"])

    async def _get_local_sessions(self) -> list[dict[str, Any]]:
        """Get local sessions for sync.

        Returns:
            List of session dictionaries.
        """
        try:
            from tinycua.storage import LocalStorageManager

            storage_manager = LocalStorageManager.get_instance()
            if storage_manager is None:
                return []
            store = storage_manager.get_store()
            if store:
                sessions = store.list_sessions()
                return [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    }
                    for s in sessions
                ]
        except Exception as e:
            logger.exception(f"Failed to get local sessions: {type(e).__name__}: {e}")
        return []

    async def _get_local_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get local messages for a session.

        Args:
            session_id: Session ID

        Returns:
            List of message dictionaries.
        """
        try:
            from tinycua.storage import LocalStorageManager

            storage_manager = LocalStorageManager.get_instance()
            if storage_manager is None:
                return []
            store = storage_manager.get_store()
            if store:
                messages = store.get_messages(uuid.UUID(session_id))
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
        except Exception as e:
            logger.exception(f"Failed to get local messages: {type(e).__name__}: {e}")
        return []

    async def _get_local_memory(self, session_id: str) -> dict[str, Any]:
        """Get local memory for a session.

        Args:
            session_id: Session ID

        Returns:
            Memory dictionary.
        """
        try:
            from tinycua.storage import LocalStorageManager

            storage_manager = LocalStorageManager.get_instance()
            if storage_manager is None:
                return {}
            store = storage_manager.get_store()
            if store:
                memory = store.get_memory(uuid.UUID(session_id))
                if memory:
                    return {"content": memory.content, "updated_at": memory.updated_at.isoformat() if memory.updated_at else None}
        except Exception as e:
            logger.exception(f"Failed to get local memory: {type(e).__name__}: {e}")
        return {}

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
        except Exception as e:
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
                    session_uuid,
                    name=session.get("name", "remote_session"),
                )
            return SyncResult(success=True, items_synced=1)
        except Exception as e:
            error_msg = f"Failed to pull session {session.get('id')}: {e}"
            logger.exception(error_msg)
            return SyncResult(success=False, errors=[error_msg])


__all__ = ["SyncEngine", "SyncResult", "OfflineQueue", "QueuedOperation", "ConflictResolver"]
