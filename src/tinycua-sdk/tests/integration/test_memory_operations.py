"""Integration tests for Memory operations."""

import pytest

from tinycua_sdk.memory.session import MemorySession
from tinycua_sdk.storage.sqlite import LocalStorage


class TestMemoryAddOperation:
    """Tests for adding memories."""

    def test_add_single_memory(self, tmp_path):
        """Can add a single memory to session."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="test-session", storage=storage)
        memory_id = session.add(
            content="Test memory content",
            memory_type="conversation",
        )
        assert memory_id is not None

    def test_add_multiple_memories(self, tmp_path):
        """Can add multiple memories."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="multi-test", storage=storage)
        id1 = session.add(content="Memory 1", memory_type="fact")
        id2 = session.add(content="Memory 2", memory_type="fact")
        assert id1 != id2

    def test_add_memory_with_metadata(self, tmp_path):
        """Can add memory with metadata."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="meta-test", storage=storage)
        memory_id = session.add(
            content="Important fact",
            memory_type="fact",
            metadata={"source": "user", "priority": "high"},
        )
        memory = session.get(memory_id)
        assert memory is not None
        assert memory["metadata_json"]["source"] == "user"
        assert memory["metadata_json"]["priority"] == "high"


class TestMemoryRetrieveOperation:
    """Tests for retrieving memories."""

    def test_retrieve_by_id(self, tmp_path):
        """Can retrieve memory by ID."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="retrieve-test", storage=storage)
        memory_id = session.add(content="Test content", memory_type="fact")
        memory = session.get(memory_id)
        assert memory is not None
        assert memory["content"] == "Test content"
        assert memory["memory_type"] == "fact"
        assert memory["session_id"] == "retrieve-test"

    def test_retrieve_nonexistent_memory(self, tmp_path):
        """Returns None for non-existent memory ID."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="retrieve-test", storage=storage)
        result = session.get("nonexistent-id")
        assert result is None


class TestMemorySearchOperation:
    """Tests for searching memories."""

    def test_search_by_content(self, tmp_path):
        """Can search memories by content."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="search-test", storage=storage)
        session.add(content="Python programming", memory_type="fact")
        results = session.search("Python")
        assert len(results) >= 1
        assert results[0]["content"] == "Python programming"

    def test_search_case_insensitive(self, tmp_path):
        """Search is case-insensitive."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="search-test", storage=storage)
        session.add(content="Python programming", memory_type="fact")
        results_lower = session.search("python")
        results_upper = session.search("PYTHON")
        assert len(results_lower) == 1
        assert len(results_upper) == 1

    def test_search_no_matches(self, tmp_path):
        """Returns empty list when no memories match."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="search-test", storage=storage)
        session.add(content="Python programming", memory_type="fact")
        results = session.search("JavaScript")
        assert results == []


class TestMemoryDeleteOperation:
    """Tests for deleting memories."""

    def test_delete_by_id(self, tmp_path):
        """Can delete memory by ID."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="delete-test", storage=storage)
        memory_id = session.add(content="To be deleted", memory_type="fact")
        result = session.delete(memory_id)
        assert result is True
        assert session.get(memory_id) is None

    def test_delete_nonexistent_memory(self, tmp_path):
        """Deleting non-existent memory returns False."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="delete-test", storage=storage)
        result = session.delete("nonexistent-id")
        assert result is False


class TestMemoryListAndClear:
    """Tests for listing and clearing memories."""

    def test_list_memories(self, tmp_path):
        """Can list all memories for a session."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="list-test", storage=storage)
        session.add(content="Memory 1", memory_type="fact")
        session.add(content="Memory 2", memory_type="conversation")
        results = session.list()
        assert len(results) == 2
        contents = {r["content"] for r in results}
        assert contents == {"Memory 1", "Memory 2"}

    def test_list_memories_by_type(self, tmp_path):
        """Can filter memories by type."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="list-test", storage=storage)
        session.add(content="Memory 1", memory_type="fact")
        session.add(content="Memory 2", memory_type="conversation")
        facts = session.list(memory_type="fact")
        assert len(facts) == 1
        assert facts[0]["content"] == "Memory 1"

    def test_clear_memories(self, tmp_path):
        """Can clear all memories for a session."""
        storage = LocalStorage(data_dir=str(tmp_path))
        session = MemorySession(session_id="clear-test", storage=storage)
        session.add(content="Memory 1", memory_type="fact")
        session.add(content="Memory 2", memory_type="fact")
        assert len(session.list()) == 2
        session.clear()
        assert len(session.list()) == 0


class TestMemoryStorePersistence:
    """Tests for MemoryStore persistence."""

    def test_store_module_available(self):
        """MemoryStore module should be importable."""
        try:
            from tinycua_sdk.memory.store import MemoryStore
            assert MemoryStore is not None
        except ImportError:
            pytest.skip("MemoryStore not yet implemented")
