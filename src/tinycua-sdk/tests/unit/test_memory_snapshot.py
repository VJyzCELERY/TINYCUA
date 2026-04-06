# Unit tests for Memory Snapshot

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from tinycua_sdk.storage.snapshot import MemorySnapshot, SnapshotManager


class TestMemorySnapshot:
    """Tests for the MemorySnapshot class."""

    def test_compute_checksum(self):
        """Test checksum computation."""
        data = {"key": "value", "number": 42}

        checksum1 = MemorySnapshot.compute_checksum(data)
        checksum2 = MemorySnapshot.compute_checksum(data)

        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex length

    def test_verify_integrity_valid(self):
        """Test integrity verification with valid checksum."""
        data = {"test": "data"}
        checksum = MemorySnapshot.compute_checksum(data)

        snapshot = MemorySnapshot(
            id="test-id",
            created_at=datetime.now(),
            data=data,
            checksum=checksum,
        )

        assert snapshot.verify_integrity() is True

    def test_verify_integrity_invalid(self):
        """Test integrity verification with invalid checksum."""
        snapshot = MemorySnapshot(
            id="test-id",
            created_at=datetime.now(),
            data={"test": "data"},
            checksum="invalid_checksum",
        )

        assert snapshot.verify_integrity() is False


class TestSnapshotManager:
    """Tests for the SnapshotManager class."""

    def test_create_snapshot(self):
        """Test creating a snapshot."""
        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_store._get_session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_store._get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock session
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid.uuid4()
        mock_session_obj.name = "Test Session"
        mock_store.get_session.return_value = mock_session_obj

        # Mock messages with proper attributes
        mock_msg = MagicMock()
        mock_msg.id = uuid.uuid4()
        mock_msg.role = "user"
        mock_msg.content = "Hello"
        mock_msg.reasoning = None
        mock_msg.turn_index = 1
        mock_msg.created_at = datetime.now()
        mock_store.list_messages.return_value = [mock_msg]

        manager = SnapshotManager(mock_store)

        with patch.object(manager, "_ensure_tables"):
            session_id = uuid.uuid4()
            snapshot = manager.create_snapshot(session_id)

        assert snapshot.id is not None
        assert snapshot.created_at is not None
        assert snapshot.checksum is not None
        assert "session_id" in snapshot.data

    def test_load_snapshot_not_found(self):
        """Test loading a non-existent snapshot."""
        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_store._get_session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_store._get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock no result found
        mock_session.execute.return_value.fetchone.return_value = None

        manager = SnapshotManager(mock_store)

        with patch.object(manager, "_ensure_tables"):
            result = manager.load_snapshot("nonexistent-id")

        assert result is None

    def test_list_snapshots(self):
        """Test listing snapshots for a session."""
        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_store._get_session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_store._get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock empty result
        mock_session.execute.return_value.fetchall.return_value = []

        manager = SnapshotManager(mock_store)

        with patch.object(manager, "_ensure_tables"):
            session_id = uuid.uuid4()
            snapshots = manager.list_snapshots(session_id)

        assert snapshots == []
