"""Integration tests for local storage operations.

These tests verify SQLite operations, session persistence, and config storage.
"""

import pytest


class TestSQLiteFileOperations:
    """Tests for SQLite file operations."""

    def test_sqlite_file_created(self, temp_db):
        """Test SQLite file is created."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        db_path = temp_db.replace("sqlite:///", "")
        import os

        assert os.path.exists(db_path)

    def test_database_schema_initialized(self, temp_db):
        """Test database schema is initialized."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        from sqlalchemy import inspect

        inspector = inspect(store.engine)
        tables = inspector.get_table_names()

        assert "sdk_sessions" in tables
        assert "messages" in tables

    def test_sqlite_is_detected(self, temp_db):
        """Test SQLite is correctly detected."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        assert store.is_sqlite is True


class TestSessionPersistence:
    """Tests for session persistence."""

    def test_session_saves_to_sqlite(self, temp_db):
        """Test session saves to SQLite."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        session = store.create_session(name="test-session")
        assert session.id is not None
        assert session.name == "test-session"

    def test_session_loads_from_sqlite(self, temp_db):
        """Test session loads from SQLite."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        created = store.create_session(name="test-session")
        loaded = store.get_session(created.id)

        assert loaded is not None
        assert loaded.id == created.id
        assert loaded.name == "test-session"

    def test_session_data_integrity(self, temp_db):
        """Test session data integrity."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        session = store.create_session(name="test-session")
        message = store.add_message(
            session_id=session.id, role="user", content="Hello"
        )

        assert message is not None
        assert message.content == "Hello"
        assert message.role == "user"

        messages = store.get_messages(session.id)
        assert len(messages) == 1
        assert messages[0].content == "Hello"


class TestConfigurationStorage:
    """Tests for configuration storage."""

    def test_config_saves_to_yaml(self, tmp_path):
        """Test config saves to YAML file."""
        from tinycua_sdk.core.config import LLMConfig, SDKConfig
        from tinycua.config.user_config import UserConfig

        config = SDKConfig(llm=LLMConfig(model="test-model"))

        config_file = tmp_path / "config.yaml"
        UserConfig.save(config, path=config_file)

        assert config_file.exists()

    def test_config_loads_from_yaml(self, tmp_path):
        """Test config loads from YAML file."""
        from tinycua_sdk.core.config import LLMConfig, SDKConfig
        from tinycua.config.user_config import UserConfig

        config = SDKConfig(llm=LLMConfig(model="test-model"))

        config_file = tmp_path / "config.yaml"
        UserConfig.save(config, path=config_file)

        loaded = UserConfig.load(path=config_file)
        assert loaded.llm.model == "test-model"

    def test_config_updates_persist(self, tmp_path):
        """Test config updates persist."""
        from tinycua_sdk.core.config import LLMConfig, SDKConfig
        from tinycua.config.user_config import UserConfig

        config = SDKConfig(llm=LLMConfig(model="original-model"))

        config_file = tmp_path / "config.yaml"
        UserConfig.save(config, path=config_file)

        loaded = UserConfig.load(path=config_file)
        updated = loaded.model_copy(update={"llm": LLMConfig(model="updated-model")})
        UserConfig.save(updated, path=config_file)

        reloaded = UserConfig.load(path=config_file)
        assert reloaded.llm.model == "updated-model"


class TestSessionStore:
    """Tests for SessionStore operations."""

    def test_create_and_list_sessions(self, temp_db):
        """Test creating and listing sessions."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        store.create_session(name="session-1")
        store.create_session(name="session-2")

        sessions = store.list_sessions()
        assert len(sessions) >= 2

    def test_update_session(self, temp_db):
        """Test updating a session."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        session = store.create_session(name="original-name")
        updated = store.update_session(session.id, name="updated-name")

        assert updated is not None
        assert updated.name == "updated-name"

    def test_delete_session(self, temp_db):
        """Test deleting a session."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(temp_db)
        store.create_tables()

        session = store.create_session(name="to-delete")
        deleted = store.delete_session(session.id)

        assert deleted is True

        loaded = store.get_session(session.id)
        assert loaded is None
