"""Unit tests for ExportManager."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tinycua.storage.export_manager import ExportManager, ExportOptions, ExportResult


class TestExportOptions:
    """Tests for ExportOptions dataclass."""

    def test_default_options(self):
        """Test default export options."""
        options = ExportOptions()
        assert options.include_sessions is True
        assert options.include_agents is True
        assert options.include_memory is True
        assert options.include_skills is True

    def test_custom_options(self):
        """Test custom export options."""
        options = ExportOptions(
            include_sessions=False,
            include_agents=True,
            include_memory=False,
            include_skills=True,
        )
        assert options.include_sessions is False
        assert options.include_agents is True
        assert options.include_memory is False
        assert options.include_skills is True


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_success_result(self):
        """Test successful export result."""
        result = ExportResult(
            success=True,
            output_path=Path("/tmp/export.json"),
            items_exported=5,
        )
        assert result.success is True
        assert result.output_path == Path("/tmp/export.json")
        assert result.items_exported == 5
        assert result.error is None

    def test_failure_result(self):
        """Test failed export result."""
        result = ExportResult(success=False, error="Disk full")
        assert result.success is False
        assert result.error == "Disk full"


class TestExportManager:
    """Tests for ExportManager."""

    @pytest.fixture
    def mock_stores(self):
        """Create mocked dependencies for ExportManager."""
        session_store = MagicMock()
        agent_manager = MagicMock()
        memory_store = MagicMock()
        skills_manager = MagicMock()
        return session_store, agent_manager, memory_store, skills_manager

    @pytest.fixture
    def export_manager(self, mock_stores):
        """Create an ExportManager with mocked stores."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores
        return ExportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )

    def test_export_manager_initializes(self, export_manager):
        """Test export manager initializes correctly."""
        assert export_manager is not None
        assert export_manager.EXPORT_VERSION == "1.0"

    def test_export_all_data(self, export_manager, mock_stores, tmp_path):
        """Test exporting all data types."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        # Mock session
        mock_session = MagicMock()
        mock_session.id = "session-1"
        mock_session.name = "Test Session"
        mock_session.user_id = None
        mock_session.created_at = None
        mock_session.updated_at = None
        mock_session.metadata = {}
        session_store.list_sessions.return_value = [mock_session]

        mock_msg = MagicMock()
        mock_msg.id = "msg-1"
        mock_msg.role = "user"
        mock_msg.content = "Hello"
        mock_msg.reasoning = None
        mock_msg.turn_index = 0
        mock_msg.created_at = None
        session_store.get_messages.return_value = [mock_msg]

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.name = "Test Agent"
        mock_agent.config.to_json.return_value = (
            '{"name": "Test Agent", "model": "gpt-4"}'
        )
        agent_manager.list_agents.return_value = [mock_agent]

        # Mock memory
        memory_store.list_keys.return_value = ["key1"]
        memory_store.get.return_value = "value1"

        # Mock skills
        mock_skill = MagicMock()
        mock_skill.name = "skill1"
        mock_skill.description = "A skill"
        mock_skill.category = "general"
        skills_manager.list_skills.return_value = [mock_skill]

        output_path = tmp_path / "export.json"
        result = export_manager.export(output_path)

        assert result.success is True
        assert result.output_path == output_path
        assert (
            result.items_exported == 4
        )  # 1 session + 1 agent + 1 memory key + 1 skill

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert "exported_at" in data
        assert len(data["data"]["sessions"]) == 1
        assert data["data"]["sessions"][0]["name"] == "Test Session"
        assert len(data["data"]["agents"]) == 1
        assert data["data"]["memory"]["key1"] == "value1"
        assert len(data["data"]["skills"]) == 1

    def test_export_selective(self, export_manager, mock_stores, tmp_path):
        """Test exporting only selected data types."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = ["key1"]
        memory_store.get.return_value = "value1"
        skills_manager.list_skills.return_value = []

        output_path = tmp_path / "export.json"
        options = ExportOptions(
            include_sessions=False,
            include_agents=False,
            include_memory=True,
            include_skills=False,
        )
        result = export_manager.export(output_path, options)

        assert result.success is True
        assert result.items_exported == 1

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "sessions" not in data["data"]
        assert "agents" not in data["data"]
        assert "memory" in data["data"]
        assert "skills" not in data["data"]

    def test_export_empty(self, export_manager, mock_stores, tmp_path):
        """Test exporting with no data."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []
        skills_manager.list_skills.return_value = []

        output_path = tmp_path / "export.json"
        result = export_manager.export(output_path)

        assert result.success is True
        assert result.items_exported == 0

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["data"]["sessions"] == []
        assert data["data"]["agents"] == []
        assert data["data"]["memory"] == {}
        assert data["data"]["skills"] == []

    def test_export_error_handling(self, export_manager, mock_stores, tmp_path):
        """Test export error handling."""
        session_store, _, _, _ = mock_stores
        session_store.list_sessions.side_effect = OSError("Database error")

        output_path = tmp_path / "export.json"
        result = export_manager.export(output_path)

        assert result.success is False
        assert result.error is not None
        assert "Database error" in result.error

    def test_export_zip(self, export_manager, mock_stores, tmp_path):
        """Test exporting as ZIP archive."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []
        skills_manager.list_skills.return_value = []

        output_path = tmp_path / "export.zip"
        result = export_manager.export_zip(output_path)

        assert result.success is True
        assert result.output_path == output_path
        assert output_path.exists()

        import zipfile

        with zipfile.ZipFile(output_path, "r") as zf:
            assert "export.json" in zf.namelist()

    def test_export_zip_failure(self, export_manager, mock_stores, tmp_path):
        """Test ZIP export failure handling."""
        session_store, _, _, _ = mock_stores
        session_store.list_sessions.side_effect = OSError("Database error")

        output_path = tmp_path / "export.zip"
        result = export_manager.export_zip(output_path)

        assert result.success is False
        assert result.error is not None

    def test_export_granular_sessions(self, export_manager, mock_stores, tmp_path):
        """Test exporting only specific sessions by ID."""
        session_store, _, _, _ = mock_stores

        mock_session1 = MagicMock()
        mock_session1.id = "session-1"
        mock_session1.name = "Session One"
        mock_session1.user_id = None
        mock_session1.created_at = None
        mock_session1.updated_at = None
        mock_session1.metadata = {}

        mock_session2 = MagicMock()
        mock_session2.id = "session-2"
        mock_session2.name = "Session Two"
        mock_session2.user_id = None
        mock_session2.created_at = None
        mock_session2.updated_at = None
        mock_session2.metadata = {}

        session_store.list_sessions.return_value = [mock_session1, mock_session2]
        session_store.get_messages.return_value = []

        output_path = tmp_path / "export.json"
        options = ExportOptions(
            include_sessions=True,
            include_agents=False,
            include_memory=False,
            include_skills=False,
            session_ids=["session-2"],
        )
        result = export_manager.export(output_path, options)

        assert result.success is True
        assert result.items_exported == 1

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["data"]["sessions"]) == 1
        assert data["data"]["sessions"][0]["id"] == "session-2"

    def test_export_granular_agents(self, export_manager, mock_stores, tmp_path):
        """Test exporting only specific agents by ID."""
        _, agent_manager, _, _ = mock_stores

        mock_agent1 = MagicMock()
        mock_agent1.id = "agent-1"
        mock_agent1.name = "Agent One"
        mock_agent1.config.to_json.return_value = '{"name": "Agent One"}'

        mock_agent2 = MagicMock()
        mock_agent2.id = "agent-2"
        mock_agent2.name = "Agent Two"
        mock_agent2.config.to_json.return_value = '{"name": "Agent Two"}'

        agent_manager.list_agents.return_value = [mock_agent1, mock_agent2]

        output_path = tmp_path / "export.json"
        options = ExportOptions(
            include_sessions=False,
            include_agents=True,
            include_memory=False,
            include_skills=False,
            agent_ids=["agent-1"],
        )
        result = export_manager.export(output_path, options)

        assert result.success is True
        assert result.items_exported == 1

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["data"]["agents"]) == 1
        assert data["data"]["agents"][0]["id"] == "agent-1"

    def test_export_agent_config_serialization_error(
        self, export_manager, mock_stores, tmp_path
    ):
        """Test export handles agent config serialization errors gracefully."""
        _, agent_manager, _, _ = mock_stores

        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.name = "Bad Agent"
        mock_agent.config.to_json.return_value = None  # Causes TypeError
        agent_manager.list_agents.return_value = [mock_agent]

        output_path = tmp_path / "export.json"
        options = ExportOptions(
            include_sessions=False,
            include_agents=True,
            include_memory=False,
            include_skills=False,
        )
        result = export_manager.export(output_path, options)

        assert result.success is True
        assert result.items_exported == 1

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["data"]["agents"][0]["config"] == {"name": "Bad Agent"}
