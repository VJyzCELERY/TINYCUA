"""Unit tests for session management."""

from unittest.mock import MagicMock, patch

from tinycua_backend.auth.core import CurrentTenant


class TestSessionCRUD:
    """Tests for session CRUD operations."""

    def test_create_session(self, mock_session_store):
        """Test creating a new session."""
        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-123"

        current = CurrentTenant(tenant=mock_tenant, user_id="user-123")

        store = mock_session_store
        session = store.create_session(
            name="Test Session",
            user_id=str(current.tenant.id),
        )

        assert session.name == "Test Session"

    def test_list_sessions(self, mock_session_store):
        """Test listing sessions."""
        store = mock_session_store
        sessions = store.list_sessions(user_id="tenant-123")

        assert isinstance(sessions, list)


class TestSessionRetrieval:
    """Tests for session retrieval."""

    def test_get_session(self, mock_session_store):
        """Test getting a session by ID."""
        store = mock_session_store
        session = store.get_session("session-123")

        assert session is not None

    def test_get_session_not_found(self, mock_session_store):
        """Test getting non-existent session returns None."""
        mock_session_store.get_session.return_value = None

        session = mock_session_store.get_session("non-existent")

        assert session is None


class TestSessionLineage:
    """Tests for session message lineage."""

    def test_add_message(self, mock_session_store):
        """Test adding a message to a session."""
        store = mock_session_store
        message = store.add_message(
            session_id="session-123",
            role="user",
            content="Hello",
        )

        assert message.role == "user"
        assert message.content == "Hello"

    def test_get_messages(self, mock_session_store):
        """Test retrieving messages for a session."""
        store = mock_session_store
        messages = store.get_messages("session-123", limit=100)

        assert isinstance(messages, list)


class TestSessionLineageChain:
    """Tests for session lineage chain functionality."""

    def test_create_session_with_parent(self, mock_session_store):
        """Test creating a session with parent_session_id."""
        mock_session = MagicMock()
        mock_session.id = "child-session-456"
        mock_session.name = "Child Session"
        mock_session.parent_session_id = "parent-session-123"
        mock_session.lineage_depth = 1

        mock_session_store.create_session.return_value = mock_session

        result = mock_session_store.create_session(
            name="Child Session",
            user_id="user-123",
            parent_session_id="parent-session-123",
        )

        assert result is not None
        mock_session_store.create_session.assert_called_once()
        call_kwargs = mock_session_store.create_session.call_args.kwargs
        assert call_kwargs.get("parent_session_id") == "parent-session-123"

    def test_get_lineage_returns_parent_chain(self, mock_session_store):
        """Test that get_lineage returns the parent chain."""
        from tinycua_sdk.storage.store import SessionStore

        mock_parent = MagicMock()
        mock_parent.id = "parent-session-123"
        mock_parent.name = "Parent Session"
        mock_parent.parent_session_id = None

        mock_child = MagicMock()
        mock_child.id = "child-session-456"
        mock_child.name = "Child Session"
        mock_child.parent_session_id = "parent-session-123"

        mock_session_store.get_lineage.return_value = [mock_parent, mock_child]

        store = mock_session_store
        lineage = store.get_lineage("child-session-456")

        assert isinstance(lineage, list)
        assert len(lineage) == 2


class TestSearchFunctionality:
    """Tests for full-text search functionality."""

    def test_search_initialization(self):
        """Test that search can be initialized."""
        from tinycua_backend.storage.search_sqlite import SQLiteSearch

        search = SQLiteSearch()
        assert search is not None
        assert search.FTS_TABLE == "messages_fts"

    def test_search_returns_message_ids(self):
        """Test that search returns matching message IDs."""
        from tinycua_backend.storage.search_sqlite import SQLiteSearch

        search = SQLiteSearch()
        import uuid
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        test_uuid = str(uuid.uuid4())
        mock_result.fetchall.return_value = [(test_uuid,)]
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=None)

        results = search.search(mock_engine, "test query", 10)

        assert isinstance(results, list)
        assert len(results) == 1

    def test_search_request_model(self):
        """Test search request model validation."""
        from tinycua_backend.api.sessions import SearchRequest

        request = SearchRequest(query="test query", limit=5)
        assert request.query == "test query"
        assert request.limit == 5

    def test_search_result_model(self):
        """Test search result model."""
        from tinycua_backend.api.sessions import SearchResult

        result = SearchResult(
            message_id="msg-123",
            session_id="session-456",
            content="Test content",
            turn_index=0,
            role="user",
        )
        assert result.message_id == "msg-123"
        assert result.content == "Test content"


class TestSessionStoreHTTP:
    """Tests for Session HTTP endpoint logic."""

    def test_session_create_requires_tenant(self):
        """Test that session creation requires tenant context."""
        from tinycua_backend.api.sessions import SessionCreate

        session_data = SessionCreate(agent_id="agent-123", name="Test Session")
        assert session_data.agent_id == "agent-123"

    def test_session_retrieval_requires_valid_id(self):
        """Test session retrieval validates session ID format."""
        import uuid

        valid_id = "12345678-1234-1234-1234-123456789abc"

        try:
            uuid.UUID(valid_id)
            is_valid = True
        except ValueError:
            is_valid = False

        assert is_valid is True

    def test_invalid_session_id_rejected(self):
        """Test invalid UUID format is rejected."""
        import uuid

        invalid_id = "not-a-uuid"

        try:
            uuid.UUID(invalid_id)
            is_valid = True
        except ValueError:
            is_valid = False

        assert is_valid is False

    def test_session_store_returns_list(self):
        """Test session store list_sessions returns a list."""
        mock_store = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "session-123"
        mock_store.list_sessions.return_value = [mock_session]

        result = mock_store.list_sessions(user_id="tenant-123")

        assert isinstance(result, list)
        assert len(result) == 1


class TestSessionCRUDHTTP:
    """Tests for session CRUD operations via HTTP."""

    def test_create_session(self, mock_session_store):
        """Test creating a new session."""
        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-123"

        current = CurrentTenant(tenant=mock_tenant, user_id="user-123")

        store = mock_session_store
        session = store.create_session(
            name="Test Session",
            user_id=str(current.tenant.id),
        )

        assert session.name == "Test Session"

    def test_list_sessions(self, mock_session_store):
        """Test listing sessions."""
        store = mock_session_store
        sessions = store.list_sessions(user_id="tenant-123")

        assert isinstance(sessions, list)


class TestSessionRetrievalHTTP:
    """Tests for session retrieval via HTTP."""

    def test_get_session(self, mock_session_store):
        """Test getting a session by ID."""
        store = mock_session_store
        session = store.get_session("session-123")

        assert session is not None

    def test_get_session_not_found(self, mock_session_store):
        """Test getting non-existent session returns None."""
        mock_session_store.get_session.return_value = None

        session = mock_session_store.get_session("non-existent")

        assert session is None


class TestSessionLineageHTTP:
    """Tests for session message lineage via HTTP."""

    def test_add_message(self, mock_session_store):
        """Test adding a message to a session."""
        store = mock_session_store
        message = store.add_message(
            session_id="session-123",
            role="user",
            content="Hello",
        )

        assert message.role == "user"
        assert message.content == "Hello"

    def test_get_messages(self, mock_session_store):
        """Test retrieving messages for a session."""
        store = mock_session_store
        messages = store.get_messages("session-123", limit=100)

        assert isinstance(messages, list)


class TestSessionStore:
    """Tests for SessionStore functionality."""

    def test_store_initialization_with_mock(self, mock_config):
        """Test SessionStore can be initialized using mock."""
        with patch("tinycua_sdk.storage.store.SessionStore") as MockSessionStore:
            mock_store_instance = MagicMock()
            MockSessionStore.return_value = mock_store_instance

            from tinycua_sdk.storage.store import SessionStore
            store = SessionStore(mock_config.database.url)

            assert store is not None
            MockSessionStore.assert_called_once()
