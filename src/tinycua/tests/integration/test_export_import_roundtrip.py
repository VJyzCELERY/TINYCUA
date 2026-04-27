"""Integration test for export/import roundtrip."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tinycua.storage.export_manager import ExportManager, ExportOptions
from tinycua.storage.import_manager import ImportManager, ImportMode
from tinycua.storage.local_memory_store import LocalMemoryStore
from tinycua.storage.local_session_store import LocalSessionStore
from tinycua.tui.agent_manager import AgentManager
from tinycua.tui.skills_manager import SkillsManager
from tinycua_sdk.storage.store import SessionStore


class TestExportImportRoundtrip:
    """End-to-end export and import roundtrip tests."""

    @pytest.fixture
    def roundtrip_stores(self, tmp_path):
        """Create real stores in a temporary directory for roundtrip testing."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        session_store = SessionStore(db_url)
        session_store.create_tables()
        local_session_store = LocalSessionStore(session_store)

        memory_db = tmp_path / "memory.db"
        memory_store = LocalMemoryStore(str(memory_db))

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        patcher = patch("tinycua.tui.agent_manager.AGENTS_DIR", agents_dir)
        patcher.start()
        agent_manager = AgentManager()

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skills_manager = SkillsManager(skill_directories=[skills_dir])

        yield local_session_store, agent_manager, memory_store, skills_manager

        patcher.stop()

    def test_roundtrip_sessions_and_memory(self, roundtrip_stores, tmp_path):
        """Test exporting and importing sessions and memory."""
        session_store, agent_manager, memory_store, skills_manager = roundtrip_stores

        # Create data
        session = session_store.create_session(name="Test Session")
        assert session is not None
        session_store.add_message(
            session_id=session.id,
            role="user",
            content="Hello",
        )
        memory_store.set("key1", "value1")

        # Export
        export_path = tmp_path / "export.json"
        export_mgr = ExportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        export_result = export_mgr.export(export_path)
        assert export_result.success is True
        assert export_path.exists()

        # Clear stores
        for sess in session_store.list_sessions():
            session_store.delete_session(sess.id)
        memory_store.clear()

        assert len(session_store.list_sessions()) == 0
        assert len(memory_store.list_keys()) == 0

        # Import
        import_mgr = ImportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        import_result = import_mgr.import_data(export_path, mode=ImportMode.REPLACE)
        assert import_result.success is True

        # Verify
        sessions = session_store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "Test Session"

        messages = session_store.get_messages(sessions[0].id)
        assert len(messages) == 1
        assert messages[0].content == "Hello"

        assert memory_store.get("key1") == "value1"

    def test_roundtrip_agents(self, roundtrip_stores, tmp_path):
        """Test exporting and importing agents."""
        session_store, agent_manager, memory_store, skills_manager = roundtrip_stores

        agent = agent_manager.create_agent(
            name="Test Agent",
            model="gpt-4",
            provider="openai",
            temperature=0.7,
            max_turns=10,
        )
        assert agent is not None

        export_path = tmp_path / "export.json"
        export_mgr = ExportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        export_result = export_mgr.export(export_path)
        assert export_result.success is True

        # Clear agents
        for existing in agent_manager.list_agents():
            agent_manager.delete_agent(existing.id)
        assert len(agent_manager.list_agents()) == 0

        import_mgr = ImportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        import_result = import_mgr.import_data(export_path, mode=ImportMode.REPLACE)
        assert import_result.success is True

        agents = agent_manager.list_agents()
        assert len(agents) == 1
        assert agents[0].name == "Test Agent"
        assert agents[0].config.model == "gpt-4"

    def test_roundtrip_selective_export(self, roundtrip_stores, tmp_path):
        """Test selective export includes only chosen data types."""
        session_store, agent_manager, memory_store, skills_manager = roundtrip_stores

        session = session_store.create_session(name="Session")
        assert session is not None
        memory_store.set("key1", "value1")

        export_path = tmp_path / "export.json"
        export_mgr = ExportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        options = ExportOptions(
            include_sessions=False,
            include_agents=False,
            include_memory=True,
            include_skills=False,
        )
        export_result = export_mgr.export(export_path, options)
        assert export_result.success is True

        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "sessions" not in data["data"]
        assert "agents" not in data["data"]
        assert "memory" in data["data"]
        assert "skills" not in data["data"]

    def test_roundtrip_replace_mode_clears_existing(self, roundtrip_stores, tmp_path):
        """Test replace mode clears existing data before import."""
        session_store, agent_manager, memory_store, skills_manager = roundtrip_stores

        old_session = session_store.create_session(name="Old Session")
        assert old_session is not None
        memory_store.set("old_key", "old_value")

        export_path = tmp_path / "export.json"
        export_mgr = ExportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        new_session = session_store.create_session(name="New Session")
        assert new_session is not None
        memory_store.set("new_key", "new_value")

        # Export only the new session and new memory
        export_result = export_mgr.export(export_path)
        assert export_result.success is True

        # Clear and add old data back
        for sess in session_store.list_sessions():
            session_store.delete_session(sess.id)
        memory_store.clear()

        old_session2 = session_store.create_session(name="Old Session 2")
        assert old_session2 is not None
        memory_store.set("old_key2", "old_value2")

        # Import in replace mode
        import_mgr = ImportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        import_result = import_mgr.import_data(export_path, mode=ImportMode.REPLACE)
        assert import_result.success is True

        sessions = session_store.list_sessions()
        assert len(sessions) == 2  # New Session + Old Session (from export)
        session_names = {s.name for s in sessions}
        assert "New Session" in session_names
        assert "Old Session" in session_names
        assert "Old Session 2" not in session_names

        assert memory_store.get("new_key") == "new_value"
        assert memory_store.get("old_key") == "old_value"
        assert memory_store.get("old_key2") is None

    def test_roundtrip_zip(self, roundtrip_stores, tmp_path):
        """Test ZIP export/import roundtrip preserves data."""
        session_store, agent_manager, memory_store, skills_manager = roundtrip_stores

        # Create data
        session = session_store.create_session(name="ZIP Session")
        assert session is not None
        session_store.add_message(
            session_id=session.id,
            role="user",
            content="Hello ZIP",
        )
        memory_store.set("zip_key", "zip_value")

        # Export to ZIP
        export_path = tmp_path / "export.zip"
        export_mgr = ExportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        export_result = export_mgr.export_zip(export_path)
        assert export_result.success is True
        assert export_path.exists()

        # Clear stores
        for sess in session_store.list_sessions():
            session_store.delete_session(sess.id)
        memory_store.clear()

        assert len(session_store.list_sessions()) == 0
        assert len(memory_store.list_keys()) == 0

        # Import from ZIP
        import_mgr = ImportManager(
            session_store=session_store,
            agent_manager=agent_manager,
            memory_store=memory_store,
            skills_manager=skills_manager,
        )
        import_result = import_mgr.import_zip(export_path, mode=ImportMode.REPLACE)
        assert import_result.success is True

        # Verify
        sessions = session_store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].name == "ZIP Session"

        messages = session_store.get_messages(sessions[0].id)
        assert len(messages) == 1
        assert messages[0].content == "Hello ZIP"

        assert memory_store.get("zip_key") == "zip_value"
