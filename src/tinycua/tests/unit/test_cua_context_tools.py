"""Tests for context tools in tinycua package."""



from tinycua_sdk.storage.store import SessionStore
from tinycua.agent.tools.context_tools import ContextTools


class TestContextTools:
    """Tests for ContextTools using the factory pattern."""

    def test_context_tools_uses_provided_store(self, tmp_path):
        """Verify DI works."""
        db_path = tmp_path / "test_di.db"
        custom_store = SessionStore(f"sqlite:///{db_path}")
        custom_store.create_tables()

        ctx = ContextTools(session_store=custom_store, session_id=None)
        store = ctx._get_store()
        assert store is custom_store

    def test_search_context_grep_no_session(self):
        """Test search returns error when no session."""
        ctx = ContextTools(session_store=None, session_id=None)
        result = ctx.search_context_grep("test")
        assert "error" in result

    def test_get_context_summary_no_session(self):
        """Test summary returns error when no session."""
        ctx = ContextTools(session_store=None, session_id=None)
        result = ctx.get_context_summary()
        assert "error" in result

    def test_get_recent_turns_no_session(self):
        """Test recent turns returns error when no session."""
        ctx = ContextTools(session_store=None, session_id=None)
        result = ctx.get_recent_turns()
        assert "error" in result
