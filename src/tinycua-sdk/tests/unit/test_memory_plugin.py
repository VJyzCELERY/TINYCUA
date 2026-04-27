import pytest
import tempfile
from pathlib import Path
from tinycua_sdk.memory.plugin import (
    MemoryPlugin,
    FileMemoryPlugin,
    InMemoryPlugin,
    SQLiteMemoryPlugin,
    get_memory_plugin,
)


class TestMemoryPluginInterface:
    """Test MemoryPlugin abstract interface."""

    def test_interface_cannot_be_instantiated(self):
        """Test that MemoryPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MemoryPlugin()


class TestInMemoryPlugin:
    """Test InMemoryPlugin class."""

    def test_initialization(self):
        """Test initializing in-memory plugin."""
        plugin = InMemoryPlugin()
        assert plugin.list_keys() == []

    def test_write_and_read(self):
        """Test writing and reading values."""
        plugin = InMemoryPlugin()
        plugin.write("name", "Alice")
        value = plugin.read("name")
        assert value == "Alice"

    def test_read_nonexistent(self):
        """Test reading non-existent key returns None."""
        plugin = InMemoryPlugin()
        value = plugin.read("nonexistent")
        assert value is None

    def test_delete(self):
        """Test deleting a key."""
        plugin = InMemoryPlugin()
        plugin.write("name", "Alice")
        result = plugin.delete("name")
        assert result["success"] is True
        assert plugin.read("name") is None

    def test_delete_nonexistent(self):
        """Test deleting non-existent key returns error."""
        plugin = InMemoryPlugin()
        result = plugin.delete("nonexistent")
        assert result["success"] is False

    def test_list_keys(self):
        """Test listing keys."""
        plugin = InMemoryPlugin()
        plugin.write("name", "Alice")
        plugin.write("age", "30")
        keys = plugin.list_keys()
        assert "name" in keys
        assert "age" in keys

    def test_clear(self):
        """Test clearing all keys."""
        plugin = InMemoryPlugin()
        plugin.write("name", "Alice")
        plugin.write("age", "30")
        plugin.clear()
        assert plugin.list_keys() == []


class TestFileMemoryPlugin:
    """Test FileMemoryPlugin class."""

    def test_initialization(self):
        """Test initializing file plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = FileMemoryPlugin(storage_path=str(Path(tmpdir) / "test.json"))
            assert plugin.list_keys() == []

    def test_persistence(self):
        """Test data persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.json")
            plugin1 = FileMemoryPlugin(storage_path=path)
            plugin1.write("name", "Alice")

            plugin2 = FileMemoryPlugin(storage_path=path)
            assert plugin2.read("name") == "Alice"


class TestSQLiteMemoryPlugin:
    """Test SQLiteMemoryPlugin class."""

    def test_initialization(self):
        """Test initializing SQLite plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            plugin = SQLiteMemoryPlugin(db_path=path)
            assert plugin.list_keys() == []

    def test_write_and_read(self):
        """Test writing and reading values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            plugin = SQLiteMemoryPlugin(db_path=path)
            plugin.write("name", "Alice")
            assert plugin.read("name") == "Alice"

    def test_persistence(self):
        """Test data persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.db")
            plugin1 = SQLiteMemoryPlugin(db_path=path)
            plugin1.write("name", "Alice")

            plugin2 = SQLiteMemoryPlugin(db_path=path)
            assert plugin2.read("name") == "Alice"


class TestGetMemoryPlugin:
    """Test get_memory_plugin factory function."""

    def test_get_file_plugin(self):
        """Test getting file plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = get_memory_plugin("file", storage_path=str(Path(tmpdir) / "test.json"))
            assert isinstance(plugin, FileMemoryPlugin)

    def test_get_memory_plugin(self):
        """Test getting in-memory plugin."""
        plugin = get_memory_plugin("memory")
        assert isinstance(plugin, InMemoryPlugin)

    def test_get_sqlite_plugin(self):
        """Test getting SQLite plugin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin = get_memory_plugin("sqlite", db_path=str(Path(tmpdir) / "test.db"))
            assert isinstance(plugin, SQLiteMemoryPlugin)

    def test_default_plugin(self):
        """Test default plugin type."""
        plugin = get_memory_plugin("invalid_type")
        assert isinstance(plugin, InMemoryPlugin)