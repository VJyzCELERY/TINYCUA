import os
import pytest
import tempfile
import threading
from pathlib import Path
from tinycua_sdk.memory.long_term import LongTermMemory


class TestLongTermMemory:
    """Test LongTermMemory class."""

    def test_initialization(self):
        """Test initializing long-term memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            assert mem._storage_path == Path(tmpdir)

    def test_write_and_read_memory(self):
        """Test writing and reading MEMORY.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            result = mem.write_memory("Test fact: The sky is blue")
            assert result["success"] is True

            content = mem.read_memory()
            assert content == "Test fact: The sky is blue"

    def test_write_and_read_user(self):
        """Test writing and reading USER.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            result = mem.write_user("User prefers dark mode")
            assert result["success"] is True

            content = mem.read_user()
            assert content == "User prefers dark mode"

    def test_read_nonexistent_file(self):
        """Test reading non-existent file returns empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            content = mem.read("NONEXISTENT.md")
            assert content == ""

    def test_write_custom_file(self):
        """Test writing to custom file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            result = mem.write("custom content", "NOTES.md")
            assert result["success"] is True

            content = mem.read("NOTES.md")
            assert content == "custom content"

    def test_update_key(self):
        """Test updating a key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            mem.write_memory("name: Alice\nage: 25")
            mem.update("name", "Bob", "MEMORY.md")
            content = mem.read_memory()
            assert "name: Bob" in content
            assert "age: 25" in content

    def test_delete_key(self):
        """Test deleting a key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            mem.write_memory("name: Alice\nage: 25")
            mem.delete("name", "MEMORY.md")
            content = mem.read_memory()
            assert "name:" not in content
            assert "age: 25" in content

    def test_file_persistence(self):
        """Test that data persists after reinitialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem1 = LongTermMemory(storage_path=tmpdir)
            mem1.write_memory("persistent fact")

            mem2 = LongTermMemory(storage_path=tmpdir)
            content = mem2.read_memory()
            assert content == "persistent fact"


class TestLongTermMemoryThreadSafety:
    """Test thread safety of LongTermMemory."""

    def test_concurrent_write(self):
        """Test concurrent writes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            errors = []

            def writer(value):
                try:
                    for i in range(20):
                        mem.write_memory(f"value {value}-{i}")
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0

    def test_concurrent_read_write(self):
        """Test concurrent read and write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = LongTermMemory(storage_path=tmpdir)
            errors = []

            def writer():
                try:
                    for i in range(30):
                        mem.write_memory(f"fact {i}")
                except Exception as e:
                    errors.append(e)

            def reader():
                try:
                    for _ in range(30):
                        _ = mem.read_memory()
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=writer),
                threading.Thread(target=reader),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0