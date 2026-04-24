"""Unit tests for ImportManager."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tinycua.storage.import_manager import (
    ImportManager,
    ImportMode,
    ImportResult,
    ImportValidation,
)


class TestImportMode:
    """Tests for ImportMode enum."""

    def test_merge_mode(self):
        """Test MERGE mode value."""
        assert ImportMode.MERGE.value == "merge"

    def test_replace_mode(self):
        """Test REPLACE mode value."""
        assert ImportMode.REPLACE.value == "replace"


class TestImportValidation:
    """Tests for ImportValidation dataclass."""

    def test_valid_validation(self):
        """Test valid validation result."""
        validation = ImportValidation(
            valid=True,
            version="1.0",
            data_types=["sessions", "agents"],
        )
        assert validation.valid is True
        assert validation.version == "1.0"
        assert validation.data_types == ["sessions", "agents"]
        assert validation.errors == []

    def test_invalid_validation(self):
        """Test invalid validation result."""
        validation = ImportValidation(
            valid=False,
            errors=["Missing version field"],
        )
        assert validation.valid is False
        assert validation.errors == ["Missing version field"]


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_success_result(self):
        """Test successful import result."""
        result = ImportResult(
            success=True,
            items_imported=5,
            warnings=["Large session count"],
        )
        assert result.success is True
        assert result.items_imported == 5
        assert result.warnings == ["Large session count"]

    def test_failure_result(self):
        """Test failed import result."""
        result = ImportResult(success=False, error="File not found")
        assert result.success is False
        assert result.error == "File not found"


class TestImportManager:
    """Tests for ImportManager."""

    @pytest.fixture
    def mock_stores(self):
        """Create mocked dependencies for ImportManager."""
        session_store = MagicMock()
        agent_manager = MagicMock()
        memory_store = MagicMock()
        skills_manager = MagicMock()
        return session_store, agent_manager, memory_store, skills_manager

    @pytest.fixture
    def import_manager(self, mock_stores):
        """Create an ImportManager with mocked stores."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores
        return ImportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )

    def _create_valid_export_file(self, path: Path, data: dict | None = None) -> None:
        """Helper to create a valid export file."""
        export_data = {
            "version": "1.0",
            "exported_at": "2026-04-19T12:00:00Z",
            "data": data or {},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f)

    def test_import_manager_initializes(self, import_manager):
        """Test import manager initializes correctly."""
        assert import_manager is not None
        assert import_manager.SUPPORTED_VERSIONS == {"1.0"}

    def test_validate_valid_file(self, import_manager, tmp_path):
        """Test validating a valid export file."""
        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"sessions": []})

        validation = import_manager.validate(export_file)

        assert validation.valid is True
        assert validation.version == "1.0"
        assert "sessions" in validation.data_types

    def test_validate_invalid_json(self, import_manager, tmp_path):
        """Test validating invalid JSON."""
        export_file = tmp_path / "export.json"
        export_file.write_text("not json")

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Invalid JSON" in e for e in validation.errors)

    def test_validate_missing_version(self, import_manager, tmp_path):
        """Test validating file with missing version."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"data": {}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Missing version" in e for e in validation.errors)

    def test_validate_unsupported_version(self, import_manager, tmp_path):
        """Test validating file with unsupported version."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "99.0", "data": {}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Unsupported version" in e for e in validation.errors)

    def test_validate_missing_data(self, import_manager, tmp_path):
        """Test validating file with missing data section."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0"}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Missing data" in e for e in validation.errors)

    def test_validate_large_session_warning(self, import_manager, tmp_path):
        """Test validation warns about large session counts."""
        export_file = tmp_path / "export.json"
        sessions = [{"name": f"session-{i}"} for i in range(101)]
        self._create_valid_export_file(export_file, {"sessions": sessions})

        validation = import_manager.validate(export_file)

        assert validation.valid is True
        assert any("Large number of sessions" in w for w in validation.warnings)

    def test_validate_file_not_found(self, import_manager, tmp_path):
        """Test validation for non-existent file."""
        export_file = tmp_path / "nonexistent.json"

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("File not found" in e for e in validation.errors)

    def test_import_merge_mode(self, import_manager, mock_stores, tmp_path):
        """Test importing in merge mode."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        mock_session = MagicMock()
        mock_session.id = "new-session-id"
        session_store.create_session.return_value = mock_session

        agent_manager.list_agents.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [
                            {"role": "user", "content": "Hello"},
                        ],
                    }
                ],
                "agents": [
                    {
                        "name": "Imported Agent",
                        "config": {
                            "model": "gpt-4",
                            "provider": "openai",
                        },
                    }
                ],
                "memory": {"key1": "value1"},
                "skills": [{"name": "skill1", "description": "A skill"}],
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.MERGE)

        assert result.success is True
        assert (
            result.items_imported == 3
        )  # 1 session + 1 agent + 1 memory (skills not imported)
        assert any("not imported" in w for w in result.warnings)
        session_store.create_session.assert_called_once()
        agent_manager.create_agent.assert_called_once()
        memory_store.set.assert_called_once_with("key1", "value1")

    def test_import_replace_mode(self, import_manager, mock_stores, tmp_path):
        """Test importing in replace mode clears memory."""
        _, _, memory_store, _ = mock_stores

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {"memory": {"key1": "value1"}},
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is True
        memory_store.clear.assert_called_once()

    def test_import_replace_mode_clears_sessions(
        self, import_manager, mock_stores, tmp_path
    ):
        """Test importing in replace mode clears existing sessions."""
        session_store, _, _, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        session_store.create_session.return_value = MagicMock(id="new-session-id")

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is True
        session_store.delete_session.assert_called_once_with("existing-session-id")
        session_store.create_session.assert_called_once()

    def test_import_replace_mode_clears_agents(
        self, import_manager, mock_stores, tmp_path
    ):
        """Test importing in replace mode clears existing agents."""
        _, agent_manager, _, _ = mock_stores

        mock_agent = MagicMock()
        mock_agent.id = "existing-agent-id"
        mock_agent.name = "Existing Agent"
        agent_manager.list_agents.return_value = [mock_agent]

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "agents": [
                    {
                        "name": "Imported Agent",
                        "config": {"model": "gpt-4", "provider": "openai"},
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is True
        agent_manager.delete_agent.assert_called_once_with("existing-agent-id")
        agent_manager.create_agent.assert_called_once()

    def test_import_skips_existing_agent(self, import_manager, mock_stores, tmp_path):
        """Test importing skips agents that already exist."""
        _, agent_manager, _, _ = mock_stores

        existing_agent = MagicMock()
        existing_agent.name = "Existing Agent"
        agent_manager.list_agents.return_value = [existing_agent]

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "agents": [
                    {
                        "name": "Existing Agent",
                        "config": {},
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert result.items_imported == 0
        assert any("already exists" in w for w in result.warnings)
        agent_manager.create_agent.assert_not_called()

    def test_import_session_error(self, import_manager, mock_stores, tmp_path):
        """Test handling session import errors."""
        session_store, _, _, _ = mock_stores
        session_store.create_session.side_effect = Exception("DB error")

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {"name": "Bad Session", "messages": []},
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert any("Failed to import session" in w for w in result.warnings)

    def test_import_invalid_file(self, import_manager, tmp_path):
        """Test importing an invalid file."""
        export_file = tmp_path / "export.json"
        export_file.write_text("not json")

        result = import_manager.import_data(export_file)

        assert result.success is False
        assert result.error is not None

    def test_import_empty_data(self, import_manager, tmp_path):
        """Test importing empty data."""
        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {})

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert result.items_imported == 0
        assert result.warnings == []

    def test_validate_returns_parsed_data(self, import_manager, tmp_path):
        """Test validation returns parsed data to avoid double file reads."""
        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"sessions": []})

        validation = import_manager.validate(export_file)

        assert validation.valid is True
        assert validation.parsed_data is not None
        assert validation.parsed_data.get("version") == "1.0"

    def test_validate_rejects_large_file(self, import_manager, tmp_path):
        """Test validation rejects files exceeding size limit."""
        export_file = tmp_path / "export.json"
        # Create a file larger than 50 MB
        large_data = {"version": "1.0", "data": {"sessions": []}}
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(large_data, f)
            # Pad to exceed limit
            f.write(" " * (import_manager.MAX_IMPORT_FILE_SIZE_BYTES + 1))

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("too large" in e.lower() for e in validation.errors)

    def test_import_replace_clears_only_present_data_types(
        self, import_manager, mock_stores, tmp_path
    ):
        """Test REPLACE clears only data types present in the import file."""
        session_store, agent_manager, memory_store, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        session_store.create_session.return_value = MagicMock(id="new-session-id")

        mock_agent = MagicMock()
        mock_agent.id = "existing-agent-id"
        agent_manager.list_agents.return_value = [mock_agent]

        export_file = tmp_path / "export.json"
        # Import file contains ONLY memory, no sessions or agents
        self._create_valid_export_file(export_file, {"memory": {"key1": "value1"}})

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is True
        session_store.delete_session.assert_not_called()
        agent_manager.delete_agent.assert_not_called()
        memory_store.clear.assert_called_once()

    def test_import_replace_clears_all_data_types_when_all_present(
        self, import_manager, mock_stores, tmp_path
    ):
        """Test REPLACE clears all data types when all are present in import."""
        session_store, agent_manager, memory_store, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        session_store.create_session.return_value = MagicMock(id="new-session-id")

        mock_agent = MagicMock()
        mock_agent.id = "existing-agent-id"
        agent_manager.list_agents.return_value = [mock_agent]

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
                "agents": [
                    {
                        "name": "Imported Agent",
                        "config": {"model": "gpt-4", "provider": "openai"},
                    }
                ],
                "memory": {"key1": "value1"},
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is True
        session_store.delete_session.assert_called_once_with("existing-session-id")
        agent_manager.delete_agent.assert_called_once_with("existing-agent-id")
        memory_store.clear.assert_called_once()

    def test_import_preserves_session_id(self, import_manager, mock_stores, tmp_path):
        """Test importing preserves original session IDs from export."""
        session_store, _, _, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "preserved-id"
        session_store.create_session.return_value = mock_session

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is True
        session_store.create_session.assert_called_once_with(
            name="Imported Session",
            user_id=None,
            session_id=__import__("uuid").UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

    def test_import_strips_api_key(self, import_manager, mock_stores, tmp_path):
        """Test importing strips api_key from agent configs."""
        _, agent_manager, _, _ = mock_stores

        agent_manager.list_agents.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "agents": [
                    {
                        "name": "Test Agent",
                        "config": {
                            "model": "gpt-4",
                            "api_key": "sk-tampered-key",
                        },
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is True
        call_kwargs = agent_manager.create_agent.call_args.kwargs
        assert call_kwargs.get("api_key") is None

    def test_import_replace_restores_backup_on_failure(
        self, import_manager, mock_stores, tmp_path
    ):
        """Test REPLACE mode restores data from backup if import fails."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        # Existing data
        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        mock_agent = MagicMock()
        mock_agent.id = "existing-agent-id"
        mock_agent.name = "Existing Agent"
        mock_agent.config.to_json.return_value = '{"name": "Existing Agent"}'

        memory_store.list_keys.return_value = ["key1"]
        memory_store.get.return_value = "value1"
        skills_manager.list_skills.return_value = []

        session_store.list_sessions.return_value = [mock_session]
        agent_manager.list_agents.return_value = [mock_agent]

        # Force import to fail after clear by monkeypatching _import_sessions
        original_import_sessions = import_manager._import_sessions

        def failing_import_sessions(*args, **kwargs):
            raise RuntimeError("DB crash after clear")

        import_manager._import_sessions = failing_import_sessions

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        # Restore original method
        import_manager._import_sessions = original_import_sessions

        assert result.success is False
        assert "data restoration also failed" in result.error.lower()
        assert session_store.delete_session.call_count >= 1

    def test_validate_rejects_invalid_sessions_type(self, import_manager, tmp_path):
        """Test validation rejects sessions that are not a list."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": {"sessions": "not-a-list"}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("sessions must be a list" in e for e in validation.errors)

    def test_validate_rejects_invalid_agents_type(self, import_manager, tmp_path):
        """Test validation rejects agents that are not a list."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": {"agents": "not-a-list"}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("agents must be a list" in e for e in validation.errors)

    def test_validate_rejects_agent_missing_name(self, import_manager, tmp_path):
        """Test validation rejects agent entries missing name."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": {"agents": [{"config": {}}]}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("missing 'name'" in e for e in validation.errors)

    def test_validate_rejects_invalid_memory_type(self, import_manager, tmp_path):
        """Test validation rejects memory that is not an object."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": {"memory": "not-an-object"}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("memory must be an object" in e for e in validation.errors)

    def test_validate_rejects_invalid_skills_type(self, import_manager, tmp_path):
        """Test validation rejects skills that are not a list."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": {"skills": "not-a-list"}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("skills must be a list" in e for e in validation.errors)

    def test_import_zip_success(self, import_manager, mock_stores, tmp_path):
        """Test importing from a ZIP archive."""
        session_store, _, _, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "new-session-id"
        session_store.create_session.return_value = mock_session

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        zip_path = tmp_path / "export.zip"
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(export_file, "export.json")

        result = import_manager.import_zip(zip_path)

        assert result.success is True
        assert result.items_imported == 1

    def test_import_zip_no_json(self, import_manager, tmp_path):
        """Test importing from a ZIP with no JSON file fails gracefully."""
        zip_path = tmp_path / "empty.zip"
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("readme.txt", "no json here")

        result = import_manager.import_zip(zip_path)

        assert result.success is False
        assert "No JSON file found" in result.error

    def test_import_zip_bad_zip(self, import_manager, tmp_path):
        """Test importing from an invalid ZIP file fails gracefully."""
        zip_path = tmp_path / "bad.zip"
        zip_path.write_text("not a zip file")

        result = import_manager.import_zip(zip_path)

        assert result.success is False
        assert "Invalid or corrupted ZIP" in result.error

    def test_import_memory_store_exception(self, import_manager, mock_stores, tmp_path):
        """Test import handles memory store exceptions gracefully."""
        _, _, memory_store, _ = mock_stores
        memory_store.set.side_effect = RuntimeError("Disk full")

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"memory": {"key1": "value1"}})

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert any("Disk full" in w for w in result.warnings)

    def test_import_skills_store_exception(self, import_manager, mock_stores, tmp_path):
        """Test import handles skills store exceptions gracefully."""
        _, _, _, skills_manager = mock_stores
        skills_manager.list_skills.side_effect = RuntimeError("Skills error")

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"skills": [{"name": "skill1"}]})

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert result.items_imported == 0

    def test_import_agent_store_exception(self, import_manager, mock_stores, tmp_path):
        """Test import handles agent store exceptions gracefully."""
        _, agent_manager, _, _ = mock_stores
        agent_manager.list_agents.side_effect = RuntimeError("Agent DB error")

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "agents": [
                    {
                        "name": "Test Agent",
                        "config": {},
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is False
        assert "Agent DB error" in result.error

    def test_validate_oserror_on_stat(self, import_manager, tmp_path, monkeypatch):
        """Test validate handles OSError during stat."""
        export_file = tmp_path / "export.json"
        export_file.write_text("{}")

        def bad_stat(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "stat", bad_stat)
        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Permission denied" in e for e in validation.errors)

    def test_validate_data_not_dict(self, import_manager, tmp_path):
        """Test validation rejects data section that is not a dict."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": "not-a-dict"}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Data section must be an object" in e for e in validation.errors)

    def test_validate_agent_item_not_dict(self, import_manager, tmp_path):
        """Test validation rejects agent list items that are not dicts."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "data": {"agents": ["not-a-dict"]}}, f)

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("agents[0] must be an object" in e for e in validation.errors)

    def test_import_zip_extraction_oserror(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test import_zip handles OSError during ZIP extraction."""
        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"sessions": []})

        zip_path = tmp_path / "export.zip"
        import zipfile as zf_mod

        with zf_mod.ZipFile(zip_path, "w", zf_mod.ZIP_DEFLATED) as zf:
            zf.write(export_file, "export.json")

        original_extract = zf_mod.ZipFile.extract

        def bad_extract(self, member, path=None, pwd=None):
            raise OSError("Extraction failed")

        monkeypatch.setattr(zf_mod.ZipFile, "extract", bad_extract)

        result = import_manager.import_zip(zip_path)

        assert result.success is False
        assert "Extraction failed" in result.error

        monkeypatch.setattr(zf_mod.ZipFile, "extract", original_extract)

    def test_import_replace_backup_failure(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test REPLACE mode handles backup export failure."""
        session_store, agent_manager, memory_store, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        agent_manager.list_agents.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"memory": {"key1": "value1"}})

        def bad_backup(*args, **kwargs):
            raise RuntimeError("Backup failed")

        monkeypatch.setattr(import_manager, "_backup_existing_data", bad_backup)

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is False
        assert "Backup failed" in result.error

    def test_import_session_create_returns_none(
        self, import_manager, mock_stores, tmp_path
    ):
        """Test importing handles create_session returning None."""
        session_store, _, _, _ = mock_stores
        session_store.create_session.return_value = None

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert result.items_imported == 0
        assert any("Failed to create session" in w for w in result.warnings)

    def test_import_data_progress_callback(self, import_manager, mock_stores, tmp_path):
        """Test import_data calls progress callback during import."""
        session_store, agent_manager, memory_store, _ = mock_stores

        mock_session = MagicMock()
        mock_session.id = "new-session-id"
        session_store.create_session.return_value = mock_session
        agent_manager.list_agents.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
                "agents": [
                    {
                        "name": "Imported Agent",
                        "config": {"model": "gpt-4", "provider": "openai"},
                    }
                ],
                "memory": {"key1": "value1"},
                "skills": [{"name": "skill1", "description": "A skill"}],
            },
        )

        progress_messages = []

        def callback(msg: str) -> None:
            progress_messages.append(msg)

        result = import_manager.import_data(
            export_file, mode=ImportMode.MERGE, progress_callback=callback
        )

        assert result.success is True
        assert any("Importing 1 sessions" in m for m in progress_messages)
        assert any("Importing 1 agents" in m for m in progress_messages)
        assert any("Importing memory entries" in m for m in progress_messages)
        assert any("Importing 1 skills" in m for m in progress_messages)

    def test_validate_oserror_on_json_load(
        self, import_manager, tmp_path, monkeypatch
    ):
        """Test validate handles OSError during json.load."""
        export_file = tmp_path / "export.json"
        export_file.write_text("{}")

        def bad_open(*args, **kwargs):
            raise OSError("Read error")

        monkeypatch.setattr("builtins.open", bad_open)
        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("Read error" in e for e in validation.errors)

    def test_validate_session_item_not_dict(self, import_manager, tmp_path):
        """Test validation rejects session list items that are not dicts."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(
                {"version": "1.0", "data": {"sessions": ["not-a-dict"]}}, f
            )

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("sessions[0] must be an object" in e for e in validation.errors)

    def test_validate_skills_item_not_dict(self, import_manager, tmp_path):
        """Test validation rejects skills list items that are not dicts."""
        export_file = tmp_path / "export.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(
                {"version": "1.0", "data": {"skills": ["not-a-dict"]}}, f
            )

        validation = import_manager.validate(export_file)

        assert validation.valid is False
        assert any("skills[0] must be an object" in e for e in validation.errors)

    def test_import_data_fallback_json_load(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test import_data falls back to json.load when parsed_data is None."""
        session_store, agent_manager, memory_store, _ = mock_stores
        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {})

        # Force validate to return parsed_data=None but valid=True
        original_validate = import_manager.validate

        def fake_validate(path):
            result = original_validate(path)
            result.parsed_data = None
            return result

        monkeypatch.setattr(import_manager, "validate", fake_validate)

        result = import_manager.import_data(export_file)

        assert result.success is True

    def test_import_data_fallback_json_load_oserror(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test import_data handles OSError in fallback json.load."""
        session_store, agent_manager, memory_store, _ = mock_stores
        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {})

        original_validate = import_manager.validate

        def fake_validate(path):
            result = original_validate(path)
            result.parsed_data = None
            return result

        monkeypatch.setattr(import_manager, "validate", fake_validate)

        real_open = open
        call_count = [0]

        def bad_open(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                # First call is in validate, let it pass
                return real_open(*args, **kwargs)
            raise OSError("Read error")

        monkeypatch.setattr("builtins.open", bad_open)

        result = import_manager.import_data(export_file)

        assert result.success is False
        assert "Read error" in result.error

    def test_import_zip_no_preferred_name(self, import_manager, mock_stores, tmp_path):
        """Test import_zip falls back to first JSON when no preferred name."""
        session_store, _, _, _ = mock_stores
        session_store.list_sessions.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {})

        zip_path = tmp_path / "export.zip"
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(export_file, "data.json")

        result = import_manager.import_zip(zip_path)

        assert result.success is True

    def test_import_zip_nested_zip_rejected(
        self, import_manager, tmp_path
    ):
        """Test import_zip rejects archives containing nested ZIP files."""
        zip_path = tmp_path / "nested.zip"
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("inner.zip", b"fake zip content")
            zf.writestr("export.json", "{}")

        result = import_manager.import_zip(zip_path)

        assert result.success is False
        assert "Nested ZIP" in result.error

    def test_import_zip_compression_ratio_rejected(
        self, import_manager, tmp_path, monkeypatch
    ):
        """Test import_zip rejects suspicious compression ratios."""
        zip_path = tmp_path / "bomb.zip"
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("export.json", "{}")

        # Monkeypatch infolist to report extreme ratio
        original_infolist = zipfile.ZipFile.infolist

        def fake_infolist(self):
            info = original_infolist(self)
            for i in info:
                i.file_size = 20000
                i.compress_size = 1
            return info

        monkeypatch.setattr(zipfile.ZipFile, "infolist", fake_infolist)

        result = import_manager.import_zip(zip_path)

        assert result.success is False
        assert "Suspicious compression" in result.error

    def test_import_zip_member_too_large(
        self, import_manager, tmp_path, monkeypatch
    ):
        """Test import_zip rejects ZIP members exceeding size limit."""
        zip_path = tmp_path / "large.zip"
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("export.json", "{}")

        original_infolist = zipfile.ZipFile.infolist

        def fake_infolist(self):
            info = original_infolist(self)
            for i in info:
                i.file_size = import_manager.MAX_IMPORT_FILE_SIZE_BYTES + 1
                i.compress_size = i.file_size
            return info

        monkeypatch.setattr(zipfile.ZipFile, "infolist", fake_infolist)

        result = import_manager.import_zip(zip_path)

        assert result.success is False
        assert "ZIP member too large" in result.error

    def test_backup_existing_data_failure(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test _backup_existing_data raises RuntimeError on export failure."""
        from tinycua.storage.export_manager import ExportManager

        def bad_export(*args, **kwargs):
            from tinycua.storage.export_manager import ExportResult

            return ExportResult(success=False, error="Disk full")

        monkeypatch.setattr(ExportManager, "export", bad_export)

        with pytest.raises(RuntimeError, match="Failed to backup"):
            import_manager._backup_existing_data()

    def test_import_agent_exception(self, import_manager, mock_stores, tmp_path):
        """Test import handles agent creation exceptions gracefully."""
        _, agent_manager, _, _ = mock_stores
        agent_manager.list_agents.return_value = []
        agent_manager.create_agent.side_effect = RuntimeError("Agent DB error")

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "agents": [
                    {
                        "name": "Bad Agent",
                        "config": {},
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file)

        assert result.success is True
        assert any("Agent DB error" in w for w in result.warnings)

    def test_restore_from_backup_failure(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test _restore_from_backup returns False on failure."""
        session_store, agent_manager, memory_store, _ = mock_stores
        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []

        # Force import_data to fail during restore
        monkeypatch.setattr(
            import_manager, "import_data", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Restore failed"))
        )

        backup_file = tmp_path / "backup.json"
        backup_file.write_text("{}")

        result = import_manager._restore_from_backup(backup_file)

        assert result is False

    def test_restore_from_backup_returns_false_on_import_result_failure(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test _restore_from_backup returns False when import_data returns failure."""
        session_store, agent_manager, memory_store, _ = mock_stores
        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []

        # Force import_data to return a failed result without raising
        monkeypatch.setattr(
            import_manager,
            "import_data",
            lambda *a, **k: ImportResult(success=False, error="Validation failed"),
        )

        backup_file = tmp_path / "backup.json"
        backup_file.write_text("{}")

        result = import_manager._restore_from_backup(backup_file)

        assert result is False

    def test_restore_from_backup_success(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test _restore_from_backup returns True when import_data succeeds."""
        session_store, agent_manager, memory_store, _ = mock_stores
        session_store.list_sessions.return_value = []
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []

        # Force import_data to return a successful result
        monkeypatch.setattr(
            import_manager,
            "import_data",
            lambda *a, **k: ImportResult(success=True, items_imported=1),
        )

        backup_file = tmp_path / "backup.json"
        backup_file.write_text("{}")

        result = import_manager._restore_from_backup(backup_file)

        assert result is True

    def test_import_replace_restore_failure_message(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test REPLACE mode reports correct error when restore also fails."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []
        skills_manager.list_skills.return_value = []

        # Backup succeeds but restore fails
        backup_file = tmp_path / "backup.json"
        self._create_valid_export_file(backup_file, {})

        def fake_backup():
            return backup_file

        monkeypatch.setattr(import_manager, "_backup_existing_data", fake_backup)
        monkeypatch.setattr(import_manager, "_restore_from_backup", lambda p: False)

        # Force import to fail after clear
        original = import_manager._import_sessions
        import_manager._import_sessions = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("DB crash"))

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        # Restore original method
        import_manager._import_sessions = original

        assert result.success is False
        assert "data restoration also failed" in result.error.lower()
        assert "data may be lost" in result.error.lower()

    def test_import_replace_restore_success_message(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test REPLACE mode reports correct error when restore succeeds."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []
        skills_manager.list_skills.return_value = []

        # Backup succeeds and restore also succeeds
        backup_file = tmp_path / "backup.json"
        self._create_valid_export_file(backup_file, {})

        def fake_backup():
            return backup_file

        monkeypatch.setattr(import_manager, "_backup_existing_data", fake_backup)
        monkeypatch.setattr(import_manager, "_restore_from_backup", lambda p: True)

        # Force import to fail after clear
        original = import_manager._import_sessions
        import_manager._import_sessions = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("DB crash"))

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(
            export_file,
            {
                "sessions": [
                    {
                        "id": "session-1",
                        "name": "Imported Session",
                        "messages": [],
                    }
                ],
            },
        )

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        # Restore original method
        import_manager._import_sessions = original

        assert result.success is False
        assert "existing data was restored" in result.error.lower()

    def test_import_replace_backup_cleanup_oserror(
        self, import_manager, mock_stores, tmp_path, monkeypatch
    ):
        """Test REPLACE mode handles backup cleanup OSError gracefully."""
        session_store, agent_manager, memory_store, skills_manager = mock_stores

        mock_session = MagicMock()
        mock_session.id = "existing-session-id"
        session_store.list_sessions.return_value = [mock_session]
        agent_manager.list_agents.return_value = []
        memory_store.list_keys.return_value = []
        skills_manager.list_skills.return_value = []

        export_file = tmp_path / "export.json"
        self._create_valid_export_file(export_file, {"memory": {"key1": "value1"}})

        original_unlink = Path.unlink

        def bad_unlink(self, missing_ok=False):
            if "tinycua_import_backups" in str(self):
                raise OSError("Cleanup failed")
            return original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", bad_unlink)

        result = import_manager.import_data(export_file, mode=ImportMode.REPLACE)

        assert result.success is True
