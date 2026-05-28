"""Tests for SessionStore extraction to storage/store.py."""

import uuid

import pytest

from tinycua_sdk.storage.store import SessionStore, get_session_store


class TestStorageMigration:
    """Tests for SessionStore migration."""

    def test_session_store_import_from_store_module(self):
        """Verify new import path works."""
        store = SessionStore("sqlite:///./test_migration.db")
        assert store is not None
        assert store.is_sqlite is True

    def test_session_store_import_from_storage_package_warns(self):
        """Verify old import emits DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="deprecated"):
            from tinycua_sdk.storage import SessionStore as OldSessionStore

            assert OldSessionStore is not None

    def test_session_store_functionality_unchanged(self):
        """Run basic CRUD to verify behavior."""
        import tempfile
        import os

        db_path = os.path.join(tempfile.gettempdir(), "test_migration_crud.db")
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()

        # Create session
        session = store.create_session(name="Migration Test", user_id="user-1")
        assert session.name == "Migration Test"

        # Add message
        message = store.add_message(
            session_id=session.id,
            role="user",
            content="Hello from migration test",
        )
        assert message is not None
        assert message.content == "Hello from migration test"
        assert message.turn_index == 0

        # Get messages
        messages = store.get_messages(session.id)
        assert len(messages) == 1

        # Get session
        retrieved = store.get_session(session.id)
        assert retrieved is not None
        assert retrieved.name == "Migration Test"

        # Cleanup
        store.delete_session(session.id)
        if os.path.exists(db_path):
            os.unlink(db_path)


class TestGetSessionStore:
    """Tests for get_session_store factory function."""

    def test_get_session_store_creates_store_on_first_call(self):
        """Verify _default_store starts None, first call creates and returns a SessionStore."""
        import tinycua_sdk.storage.store as store_module

        # Reset the default store for this test
        original = store_module._default_store
        store_module._default_store = None

        try:
            result = get_session_store()
            assert isinstance(result, SessionStore)
        finally:
            store_module._default_store = original

    def test_get_session_store_creates_tables_on_first_use(self):
        """Verify create_tables() is called during first initialization."""
        import tinycua_sdk.storage.store as store_module

        # Reset the default store for this test
        original = store_module._default_store
        store_module._default_store = None

        try:
            result = get_session_store()
            # If create_tables was called, the tables should exist
            from tinycua_sdk.storage.models import Base

            inspector = result.engine.dialect.inspect(result.engine)
            tables = inspector.get_table_names()
            assert "sdk_sessions" in tables
            assert "messages" in tables
        finally:
            store_module._default_store = original

    def test_get_session_store_returns_same_instance_on_subsequent_calls(self):
        """Verify singleton behavior."""
        import tinycua_sdk.storage.store as store_module

        # Reset the default store for this test
        original = store_module._default_store
        store_module._default_store = None

        try:
            store1 = get_session_store()
            store2 = get_session_store()
            assert store1 is store2
        finally:
            store_module._default_store = original

    def test_get_session_store_with_custom_url(self):
        """Verify custom URL creates new instance."""
        import tempfile
        import os

        db_path = os.path.join(tempfile.gettempdir(), "test_custom_url.db")
        store = get_session_store(database_url=f"sqlite:///{db_path}")
        assert isinstance(store, SessionStore)
        assert store.database_url == f"sqlite:///{db_path}"

        # Custom URL should create a new instance, not cached
        store2 = get_session_store(database_url=f"sqlite:///{db_path}")
        assert store is not store2

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
