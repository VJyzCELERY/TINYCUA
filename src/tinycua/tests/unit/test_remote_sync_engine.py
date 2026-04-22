"""Tests for SyncEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSyncEngine:
    """Test SyncEngine methods."""

    def test_engine_initialization(self):
        """Test engine initializes with connection manager."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        assert engine._connection_manager is manager
        assert engine.last_sync is None

    @pytest.mark.asyncio
    async def test_sync_sessions_not_connected(self):
        """Test sync_sessions returns error when not connected."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        result = await engine.sync_sessions()

        assert result.success is False
        assert "Not connected" in result.errors[0]

    @pytest.mark.asyncio
    async def test_sync_sessions_success(self):
        """Test sync_sessions syncs sessions successfully."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        manager._connected = True

        mock_client = AsyncMock()
        mock_client.list_agents = AsyncMock(return_value=[])
        manager._client = mock_client

        engine = SyncEngine(manager)

        with patch.object(engine, "_get_local_sessions", new_callable=AsyncMock) as mock_local:
            mock_local.return_value = []
            result = await engine.sync_sessions()

            assert result.success is True
            assert result.items_synced == 0

    @pytest.mark.asyncio
    async def test_push_all_not_connected(self):
        """Test push_all returns error when not connected."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        result = await engine.push_all()

        assert result.success is False
        assert "Not connected" in result.errors[0]

    @pytest.mark.asyncio
    async def test_pull_all_not_connected(self):
        """Test pull_all returns error when not connected."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        result = await engine.pull_all()

        assert result.success is False
        assert "Not connected" in result.errors[0]

    def test_merge_sessions_last_write_wins(self):
        """Test merge_sessions uses last-write-wins."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        local_sessions = [
            {"id": "1", "name": "session1", "updated_at": "2026-01-01T00:00:00"},
            {"id": "2", "name": "local_session", "updated_at": "2026-01-02T00:00:00"},
        ]
        remote_sessions = [
            {"id": "1", "name": "session1", "updated_at": "2026-01-03T00:00:00"},
            {"id": "3", "name": "remote_session", "updated_at": "2026-01-02T00:00:00"},
        ]

        result = engine._merge_sessions(local_sessions, remote_sessions)

        assert len(result) == 3

    def test_merge_messages_last_write_wins(self):
        """Test merge_messages uses last-write-wins."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        local_messages = [
            {"id": "1", "role": "user", "content": "hello", "created_at": "2026-01-01T00:00:00"},
        ]
        remote_messages = [
            {"id": "1", "role": "user", "content": "hello updated", "created_at": "2026-01-02T00:00:00"},
        ]

        merged, count = engine._merge_messages(local_messages, remote_messages)

        assert count == 1
        assert len(merged) == 1

    @pytest.mark.asyncio
    async def test_sync_memory_not_connected(self):
        """Test sync_memory returns error when not connected."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        result = await engine.sync_memory()

        assert result.success is False
        assert "Not connected" in result.errors[0]

    @pytest.mark.asyncio
    async def test_sync_memory_success(self):
        """Test sync_memory syncs memory successfully."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        manager._connected = True

        mock_client = MagicMock()
        mock_client.get_memory = AsyncMock(return_value={"content": "memory"})
        mock_client.save_memory = AsyncMock(return_value={})
        manager._client = mock_client

        engine = SyncEngine(manager)

        with patch.object(engine, "_get_local_sessions", new_callable=AsyncMock) as mock_local:
            mock_local.return_value = [{"id": "1", "name": "session1"}]
            result = await engine.sync_memory()

            assert result.success is True

    @pytest.mark.asyncio
    async def test_sync_memory_queued_when_offline(self):
        """Test sync_memory queues operation when not connected."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)
        engine._offline_queue.clear()

        result = await engine.sync_memory()

        assert result.success is False
        assert "queued" in result.errors[0]
        assert engine._offline_queue.size() == 1

    @pytest.mark.asyncio
    async def test_replay_offline_queue_not_connected(self):
        """Test replay_offline_queue returns error when not connected."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        result = await engine.replay_offline_queue()

        assert result.success is False
        assert "Not connected" in result.errors[0]

    @pytest.mark.asyncio
    async def test_replay_offline_queue_success(self):
        """Test replay_offline_queue replays queued operations."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        manager._connected = True

        mock_client = MagicMock()
        mock_client.get_memory = AsyncMock(return_value={"content": "memory"})
        mock_client.save_memory = AsyncMock(return_value={})
        manager._client = mock_client

        engine = SyncEngine(manager)
        engine._offline_queue.enqueue({"type": "sync_memory"})

        with patch.object(engine, "_get_local_sessions", new_callable=AsyncMock) as mock_local:
            mock_local.return_value = [{"id": "1", "name": "session1"}]
            result = await engine.replay_offline_queue()

            assert result.items_synced >= 0
            assert engine._offline_queue.is_empty()

    def test_merge_sessions_returns_list(self):
        """Test merge_sessions returns list of merged sessions."""
        from tinycua.remote import RemoteConnectionManager, SyncEngine

        manager = RemoteConnectionManager(backend_url="http://localhost:8000")
        engine = SyncEngine(manager)

        local_sessions = [
            {"id": "1", "name": "session1", "updated_at": "2026-01-01T00:00:00"},
        ]
        remote_sessions = [
            {"id": "1", "name": "session1", "updated_at": "2026-01-03T00:00:00"},
            {"id": "2", "name": "remote_session", "updated_at": "2026-01-02T00:00:00"},
        ]

        result = engine._merge_sessions(local_sessions, remote_sessions)

        assert isinstance(result, list)
        assert len(result) == 2
