"""Tests for centralized SessionStore usage in context_tools.py."""

import uuid

import pytest

from tinycua_sdk.storage.store import SessionStore, get_session_store
from tinycua_sdk.tools.context_tools import ContextTools


class TestContextToolsStoreUsage:
    """Tests for ContextTools using the factory pattern."""

    def test_context_tools_uses_default_store_when_none_provided(self, tmp_path):
        """Verify factory is used when no store is provided."""
        import tinycua_sdk.storage.store as store_module

        # Reset default store
        original = store_module._default_store
        store_module._default_store = None

        try:
            ctx = ContextTools(session_store=None, session_id=None)
            store = ctx._get_store()
            assert isinstance(store, SessionStore)
        finally:
            store_module._default_store = original

    def test_context_tools_uses_provided_store(self, tmp_path):
        """Verify DI works."""
        db_path = tmp_path / "test_di.db"
        custom_store = SessionStore(f"sqlite:///{db_path}")
        custom_store.create_tables()

        ctx = ContextTools(session_store=custom_store, session_id=None)
        store = ctx._get_store()
        assert store is custom_store


class TestGetSessionStoreFactory:
    """Tests for get_session_store factory function."""

    def test_get_session_store_creates_store_on_first_call(self):
        """Verify _default_store starts None, first call creates and returns a SessionStore."""
        import tinycua_sdk.storage.store as store_module

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

        original = store_module._default_store
        store_module._default_store = None

        try:
            result = get_session_store()
            inspector = result.engine.dialect.inspect(result.engine)
            tables = inspector.get_table_names()
            assert "sdk_sessions" in tables
            assert "messages" in tables
        finally:
            store_module._default_store = original

    def test_get_session_store_returns_same_instance_on_subsequent_calls(self):
        """Verify singleton behavior."""
        import tinycua_sdk.storage.store as store_module

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

        db_path = os.path.join(tempfile.gettempdir(), "test_ctx_custom.db")
        store = get_session_store(database_url=f"sqlite:///{db_path}")
        assert isinstance(store, SessionStore)
        assert store.database_url == f"sqlite:///{db_path}"

        # Custom URL creates new instance, not cached
        store2 = get_session_store(database_url=f"sqlite:///{db_path}")
        assert store is not store2

        if os.path.exists(db_path):
            os.unlink(db_path)
