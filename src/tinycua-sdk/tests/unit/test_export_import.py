"""Unit tests for Exporter and Importer."""

import io
import json
import os
import tempfile
import pytest
import zipfile

from tinycua_sdk.storage.sqlite import LocalStorage
from tinycua_sdk.storage.export import Exporter, CURRENT_VERSION as EXPORT_VERSION
from tinycua_sdk.storage.importer import Importer, CURRENT_VERSION as IMPORT_VERSION, MIN_VERSION


class TestExporter:
    """Test cases for Exporter class."""

    @pytest.fixture
    def storage(self):
        """Create a temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalStorage(tmpdir)

    @pytest.fixture
    def exporter(self, storage):
        """Create an exporter instance."""
        return Exporter(storage)

    def test_export_json(self, storage, exporter):
        """Test exporting to JSON format."""
        storage.save_session("session-1", "Session 1")
        storage.save_agent("agent-1", "Agent 1", {"model": "gpt-4"})
        storage.save_memory("memory-1", "short_term", "content")
        
        result = exporter.export_json()
        
        assert result["version"] == EXPORT_VERSION
        assert "exported_at" in result
        assert len(result["sessions"]) == 1
        assert len(result["agents"]) == 1
        assert len(result["memory"]) == 1

    def test_export_zip(self, storage, exporter):
        """Test exporting to ZIP format."""
        storage.save_session("session-1", "Session 1")
        
        result = exporter.export_zip()
        
        assert result["version"] == EXPORT_VERSION
        assert "zip_data" in result
        assert result["size"] > 0

    def test_export_zip_contents(self, storage, exporter):
        """Test that ZIP contains required files."""
        storage.save_session("session-1", "Session 1")
        
        result = exporter.export_zip()
        
        buffer = io.BytesIO(result["zip_data"])
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            assert "data.json" in names
            assert "MEMORY.md" in names
            assert "USER.md" in names

    def test_export_to_file_json(self, storage, exporter):
        """Test exporting to JSON file."""
        storage.save_session("session-1", "Session 1")
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        
        try:
            result = exporter.export_to_file(filepath)
            assert result["format"] == "json"
            assert os.path.exists(filepath)
            
            with open(filepath, "r") as f:
                data = json.load(f)
                assert len(data["sessions"]) == 1
        finally:
            os.unlink(filepath)

    def test_export_to_file_zip(self, storage, exporter):
        """Test exporting to ZIP file."""
        storage.save_session("session-1", "Session 1")
        
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            filepath = f.name
        
        try:
            result = exporter.export_to_file(filepath)
            assert result["format"] == "zip"
            assert os.path.exists(filepath)
            assert result["size"] > 0
        finally:
            os.unlink(filepath)


class TestImporter:
    """Test cases for Importer class."""

    @pytest.fixture
    def storage(self):
        """Create a temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalStorage(tmpdir)

    @pytest.fixture
    def importer(self, storage):
        """Create an importer instance."""
        return Importer(storage)

    def test_validate_import_valid(self, importer):
        """Test validating valid import data."""
        data = {
            "version": IMPORT_VERSION,
            "sessions": [],
            "agents": [],
            "memory": [],
        }
        
        result = importer.validate_import(data)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_import_missing_version(self, importer):
        """Test validating data without version."""
        data = {
            "sessions": [],
            "agents": [],
            "memory": [],
        }
        
        result = importer.validate_import(data)
        
        assert result["valid"] is False
        assert "version" in str(result["errors"])

    def test_validate_import_old_version(self, importer):
        """Test validating data with old version."""
        data = {
            "version": "0.1.0",
            "sessions": [],
            "agents": [],
            "memory": [],
        }
        
        result = importer.validate_import(data)
        
        assert result["valid"] is False

    def test_validate_import_wrong_types(self, importer):
        """Test validating data with wrong types."""
        data = {
            "version": IMPORT_VERSION,
            "sessions": "not a list",
            "agents": [],
            "memory": [],
        }
        
        result = importer.validate_import(data)
        
        assert result["valid"] is False

    def test_import_json_merge_mode(self, storage, importer):
        """Test importing JSON in merge mode."""
        storage.save_session("session-1", "Session 1")
        
        data = {
            "version": IMPORT_VERSION,
            "sessions": [
                {"id": "session-2", "name": "Session 2"},
            ],
            "agents": [],
            "memory": [],
        }
        
        result = importer.import_json(data, mode="merge")
        
        assert result["success"] is True
        assert result["imported"]["sessions"] == 1
        sessions = storage.list_sessions()
        assert len(sessions) == 2

    def test_import_json_replace_mode(self, storage, importer):
        """Test importing JSON in replace mode."""
        storage.save_session("session-1", "Session 1")
        
        data = {
            "version": IMPORT_VERSION,
            "sessions": [
                {"id": "session-2", "name": "Session 2"},
            ],
            "agents": [],
            "memory": [],
        }
        
        result = importer.import_json(data, mode="replace")
        
        assert result["success"] is True
        assert result["imported"]["sessions"] == 1
        
        sessions = storage.list_sessions()
        assert sessions[0]["name"] == "Session 2"

    def test_import_zip(self, storage, importer):
        """Test importing from ZIP format."""
        storage.save_session("session-1", "Session 1")
        
        exporter = Exporter(storage)
        zip_result = exporter.export_zip()
        
        result = importer.import_zip(zip_result["zip_data"], mode="merge")
        
        assert result["success"] is True

    def test_import_from_file_json(self, storage, importer):
        """Test importing from JSON file."""
        storage.save_session("session-1", "Session 1")
        
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            filepath = f.name
            json.dump({
                "version": IMPORT_VERSION,
                "sessions": [{"id": "session-2", "name": "Session 2"}],
                "agents": [],
                "memory": [],
            }, f)
        
        try:
            result = importer.import_from_file(filepath, mode="merge")
            assert result["success"] is True
            assert result["imported"]["sessions"] == 1
            sessions = storage.list_sessions()
            assert len(sessions) == 2
        finally:
            os.unlink(filepath)

    def test_import_from_file_zip(self, storage, importer):
        """Test importing from ZIP file."""
        storage.save_session("session-1", "Session 1")
        
        exporter = Exporter(storage)
        
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            filepath = f.name
            zip_result = exporter.export_zip()
            f.write(zip_result["zip_data"])
        
        try:
            result = importer.import_from_file(filepath, mode="merge")
            assert result["success"] is True
        finally:
            os.unlink(filepath)

    def test_import_invalid_zip(self, importer):
        """Test importing invalid ZIP."""
        result = importer.import_zip(b"not a zip")
        
        assert result["success"] is False
        assert len(result["errors"]) > 0
