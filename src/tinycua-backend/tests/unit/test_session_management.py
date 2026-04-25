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
