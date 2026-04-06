"""Memory snapshot for frozen state."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tinycua_sdk.storage.store import SessionStore


@dataclass
class MemorySnapshot:
    """Immutable memory snapshot.

    Represents a frozen point-in-time view of session memory
    that cannot be modified after creation.

    Attributes:
        id: Unique identifier for the snapshot
        created_at: When the snapshot was created
        data: The snapshot data
        checksum: SHA256 checksum for integrity verification
    """

    id: str
    created_at: datetime
    data: dict[str, Any]
    checksum: str

    @staticmethod
    def compute_checksum(data: dict[str, Any]) -> str:
        """Compute SHA256 checksum for data.

        Args:
            data: Data to compute checksum for

        Returns:
            Hexadecimal checksum string
        """
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify snapshot integrity using checksum.

        Returns:
            True if checksum matches, False otherwise
        """
        expected = self.compute_checksum(self.data)
        return self.checksum == expected


class SnapshotError(Exception):
    """Base exception for snapshot operations."""

    pass


class SnapshotManager:
    """Manages memory snapshots.

    Provides creation, loading, and listing of frozen memory snapshots.
    """

    def __init__(self, store: SessionStore):
        """Initialize with session store.

        Args:
            store: SessionStore instance
        """
        self.store = store
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure snapshot tables exist."""
        from sqlalchemy import text

        with self.store._get_session() as session:
            # Create snapshots table if not exists
            session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    data JSON NOT NULL,
                    checksum TEXT NOT NULL
                )
            """)
            )
            session.commit()

    def create_snapshot(
        self,
        session_id: uuid.UUID,
        metadata: dict[str, Any] | None = None,
    ) -> MemorySnapshot:
        """Create a frozen snapshot of current memory state.

        Args:
            session_id: Session ID
            metadata: Optional metadata about the snapshot

        Returns:
            Created MemorySnapshot

        Raises:
            SnapshotError: If snapshot creation fails
        """
        try:
            # Get current session state
            session = self.store.get_session(session_id)
            if session is None:
                raise SnapshotError(f"Session {session_id} not found")

            messages = self.store.list_messages(session_id)

            # Build snapshot data
            snapshot_data = {
                "session_id": str(session_id),
                "session_name": session.name,
                "messages": [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "reasoning": m.reasoning,
                        "turn_index": m.turn_index,
                        "created_at": m.created_at.isoformat()
                        if m.created_at
                        else None,
                    }
                    for m in messages
                ],
                "metadata": metadata or {},
            }

            # Compute checksum
            checksum = MemorySnapshot.compute_checksum(snapshot_data)

            # Create snapshot
            snapshot = MemorySnapshot(
                id=str(uuid.uuid4()),
                created_at=datetime.now(),
                data=snapshot_data,
                checksum=checksum,
            )

            # Save to database
            self._save_snapshot(snapshot)

            return snapshot

        except Exception as e:
            if isinstance(e, SnapshotError):
                raise
            raise SnapshotError(f"Failed to create snapshot: {e}")

    def _save_snapshot(self, snapshot: MemorySnapshot) -> None:
        """Save snapshot to database."""
        from sqlalchemy import text

        with self.store._get_session() as session:
            session.execute(
                text("""
                    INSERT INTO snapshots (id, session_id, created_at, data, checksum)
                    VALUES (:id, :session_id, :created_at, :data, :checksum)
                """),
                {
                    "id": snapshot.id,
                    "session_id": snapshot.data["session_id"],
                    "created_at": snapshot.created_at,
                    "data": json.dumps(snapshot.data),
                    "checksum": snapshot.checksum,
                },
            )
            session.commit()

    def load_snapshot(self, snapshot_id: str) -> MemorySnapshot | None:
        """Load a snapshot from storage.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Loaded snapshot or None

        Raises:
            SnapshotError: If snapshot is corrupted
        """
        from sqlalchemy import text

        with self.store._get_session() as session:
            result = session.execute(
                text(
                    "SELECT id, created_at, data, checksum FROM snapshots "
                    "WHERE id = :id"
                ),
                {"id": snapshot_id},
            )
            row = result.fetchone()

        if row is None:
            return None

        try:
            data = json.loads(row.data)
            snapshot = MemorySnapshot(
                id=row.id,
                created_at=row.created_at,
                data=data,
                checksum=row.checksum,
            )

            # Verify integrity
            if not snapshot.verify_integrity():
                raise SnapshotError(f"Snapshot {snapshot_id} integrity check failed")

            return snapshot

        except json.JSONDecodeError as e:
            raise SnapshotError(f"Failed to parse snapshot data: {e}")

    def list_snapshots(self, session_id: uuid.UUID) -> list[MemorySnapshot]:
        """List all snapshots for a session.

        Args:
            session_id: Session ID

        Returns:
            List of snapshots (without full data loaded)
        """
        from sqlalchemy import text

        with self.store._get_session() as session:
            result = session.execute(
                text("""
                    SELECT id, created_at, data, checksum
                    FROM snapshots
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC
                """),
                {"session_id": str(session_id)},
            )
            rows = result.fetchall()

        snapshots = []
        for row in rows:
            data = json.loads(row.data)
            snapshots.append(
                MemorySnapshot(
                    id=row.id,
                    created_at=row.created_at,
                    data=data,
                    checksum=row.checksum,
                )
            )

        return snapshots
