"""Tests for memory and session tools."""

import pytest
import tempfile
from pathlib import Path


class TestLocalMemoryBackend:
    """Test local memory storage."""

    def test_memory_set_and_get(self):
        """Test setting and getting values."""
        from tinycua_sdk.tools.memory import LocalMemoryBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))

            result = storage.set("name", "Bob")
            assert result["success"] is True

            value, found = storage.get("name")
            assert found is True
            assert value == "Bob"

    def test_memory_delete(self):
        """Test deleting values."""
        from tinycua_sdk.tools.memory import LocalMemoryBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))

            storage.set("name", "Bob")
            result = storage.delete("name")
            assert result["success"] is True

            _, found = storage.get("name")
            assert found is False

    def test_memory_list_keys(self):
        """Test listing keys."""
        from tinycua_sdk.tools.memory import LocalMemoryBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))

            storage.set("name", "Bob")
            storage.set("age", "25")

            keys = storage.list_keys()
            assert "name" in keys
            assert "age" in keys

    def test_memory_clear(self):
        """Test clearing all memory."""
        from tinycua_sdk.tools.memory import LocalMemoryBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))

            storage.set("name", "Bob")
            storage.set("age", "25")

            result = storage.clear()
            assert result["success"] is True

            keys = storage.list_keys()
            assert len(keys) == 0


class TestHybridMemoryBackend:
    """Test hybrid memory backend."""

    def test_local_only_fallback(self):
        """Test that hybrid falls back to local when remote unavailable."""
        from tinycua_sdk.tools.memory import HybridMemoryBackend, LocalMemoryBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = HybridMemoryBackend(
                backend_url="http://localhost:9999",
                local_storage_path=str(Path(tmpdir) / "memory.json"),
            )

            assert isinstance(backend._local, LocalMemoryBackend)

            result = backend.set("name", "Bob")
            assert result["success"] is True

            value, found = backend.get("name")
            assert found is True
            assert value == "Bob"


class TestMemoryTools:
    """Test memory tool functions."""

    def test_tools_with_invoke(self):
        """Test memory tools using invoke method."""
        from tinycua_sdk.tools.memory import LocalMemoryBackend
        from tinycua_sdk.tools.memory_tools import (
            forget,
            list_memory,
            recall,
            remember,
            set_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))
            set_memory_backend(storage)

            remember.invoke(key="name", value="Bob")
            result = recall.invoke(key="name")
            assert result["found"] is True
            assert result["value"] == "Bob"

            result = list_memory.invoke()
            assert "name" in result["keys"]

            forget.invoke(key="name")
            result = recall.invoke(key="name")
            assert result["found"] is False


class TestSessionUtils:
    """Test session utilities."""

    def test_session_create_and_save(self):
        """Test creating and saving sessions."""
        from tinycua_sdk.utils import (
            create_session,
            load_session,
            delete_session,
        )
        from tinycua_sdk.tools.memory import LocalMemoryBackend
        from tinycua_sdk.tools.memory_tools import (
            set_memory_backend,
            reset_memory_backend,
        )
        import tempfile
        from pathlib import Path

        reset_memory_backend()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))
            set_memory_backend(storage)

            result = create_session(name="Test Session")
            assert result["success"] is True
            session_id = result["session_id"]

            loaded = load_session(session_id=session_id)
            assert loaded["success"] is True
            assert loaded["name"] == "Test Session"

            deleted = delete_session(session_id=session_id)
            assert deleted["success"] is True
