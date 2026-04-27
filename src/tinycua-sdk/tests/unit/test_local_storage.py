"""Unit tests for LocalStorage."""

import os
import tempfile
import pytest

from tinycua_sdk.storage.sqlite import LocalStorage, CURRENT_VERSION


class TestLocalStorage:
    """Test cases for LocalStorage class."""

    @pytest.fixture
    def storage(self):
        """Create a temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalStorage(tmpdir)

    def test_init_creates_directory(self, storage):
        """Test that storage creates data directory."""
        assert os.path.exists(storage.data_dir)

    def test_init_creates_database(self, storage):
        """Test that storage creates SQLite database."""
        assert os.path.exists(storage.db_path)

    def test_save_and_load_session(self, storage):
        """Test saving and loading a session."""
        session = storage.save_session(
            session_id="test-session-1",
            name="Test Session",
            user_id="user-1",
        )
        assert session["id"] == "test-session-1"
        assert session["name"] == "Test Session"
        assert session["user_id"] == "user-1"

    def test_load_nonexistent_session(self, storage):
        """Test loading a session that doesn't exist."""
        result = storage.load_session("nonexistent")
        assert result is None

    def test_list_sessions(self, storage):
        """Test listing all sessions."""
        storage.save_session("session-1", "Session 1")
        storage.save_session("session-2", "Session 2")
        
        sessions = storage.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_filtered_by_user(self, storage):
        """Test listing sessions filtered by user_id."""
        storage.save_session("session-1", "Session 1", user_id="user-1")
        storage.save_session("session-2", "Session 2", user_id="user-2")
        
        sessions = storage.list_sessions(user_id="user-1")
        assert len(sessions) == 1
        assert sessions[0]["user_id"] == "user-1"

    def test_delete_session(self, storage):
        """Test deleting a session."""
        storage.save_session("session-1", "Session 1")
        
        result = storage.delete_session("session-1")
        assert result is True
        
        result = storage.load_session("session-1")
        assert result is None

    def test_save_and_load_agent(self, storage):
        """Test saving and loading an agent."""
        agent = storage.save_agent(
            agent_id="test-agent-1",
            name="Test Agent",
            config={"model": "gpt-4"},
        )
        assert agent["id"] == "test-agent-1"
        assert agent["name"] == "Test Agent"

    def test_list_agents(self, storage):
        """Test listing all agents."""
        storage.save_agent("agent-1", "Agent 1", {})
        storage.save_agent("agent-2", "Agent 2", {})
        
        agents = storage.list_agents()
        assert len(agents) == 2

    def test_delete_agent(self, storage):
        """Test deleting an agent."""
        storage.save_agent("agent-1", "Agent 1", {})
        
        result = storage.delete_agent("agent-1")
        assert result is True

    def test_save_and_load_memory(self, storage):
        """Test saving and loading memory."""
        memory = storage.save_memory(
            memory_id="memory-1",
            memory_type="short_term",
            content="Test memory content",
            session_id="session-1",
        )
        assert memory["id"] == "memory-1"
        assert memory["memory_type"] == "short_term"
        assert memory["content"] == "Test memory content"

    def test_list_memory_filtered(self, storage):
        """Test listing memory with filters."""
        storage.save_memory("memory-1", "short_term", "content 1", session_id="s1")
        storage.save_memory("memory-2", "long_term", "content 2", session_id="s1")
        storage.save_memory("memory-3", "short_term", "content 3", session_id="s2")
        
        result = storage.list_memory(session_id="s1")
        assert len(result) == 2
        
        result = storage.list_memory(memory_type="long_term")
        assert len(result) == 1

    def test_export_all(self, storage):
        """Test exporting all data."""
        storage.save_session("session-1", "Session 1")
        storage.save_agent("agent-1", "Agent 1", {})
        storage.save_memory("memory-1", "short_term", "content")
        
        data = storage.export_all()
        assert len(data["sessions"]) == 1
        assert len(data["agents"]) == 1
        assert len(data["memory"]) == 1

    def test_import_data_merge_mode(self, storage):
        """Test importing data in merge mode."""
        storage.save_session("session-1", "Session 1")
        
        data = {
            "sessions": [
                {"id": "session-2", "name": "Session 2"},
            ],
            "agents": [],
            "memory": [],
        }
        
        result = storage.import_data(data, mode="merge")
        assert result["sessions"] == 1
        sessions = storage.list_sessions()
        assert len(sessions) == 2

    def test_import_data_replace_mode(self, storage):
        """Test importing data in replace mode."""
        storage.save_session("session-1", "Session 1")
        
        data = {
            "sessions": [
                {"id": "session-2", "name": "Session 2"},
            ],
            "agents": [],
            "memory": [],
        }
        
        result = storage.import_data(data, mode="replace")
        assert result["sessions"] == 1
        
        sessions = storage.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["name"] == "Session 2"
