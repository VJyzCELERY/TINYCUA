"""Tests for unified storage layer."""

import uuid

import pytest

from tinycua_sdk.storage import SessionStore


class TestSessionModel:
    """Tests for Session model via SessionStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a test store with SQLite."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()
        return store

    def test_session_creation(self, store):
        """Test creating a session via store."""
        session = store.create_session(name="Test Session", user_id="user-123")
        assert session.name == "Test Session"
        assert session.user_id == "user-123"
        assert session.has_summary is False
        assert session.summary_md is None
        assert session.full_context_md is None

    def test_session_default_values(self, store):
        """Test session has correct defaults via store."""
        session = store.create_session(name="Test")
        assert session.has_summary is False


class TestMessageModel:
    """Tests for Message model via SessionStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a test store with SQLite."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()
        return store

    def test_message_creation(self, store):
        """Test creating a message via store."""
        session = store.create_session(name="Test")
        message = store.add_message(
            session_id=session.id,
            role="user",
            content="Hello",
        )
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.turn_index == 1

    def test_message_reasoning_field(self, store):
        """Test message reasoning field."""
        session = store.create_session(name="Test")
        message = store.add_message(
            session_id=session.id,
            role="assistant",
            content="Hello!",
            reasoning="Thinking about greeting",
        )
        assert message.reasoning == "Thinking about greeting"

    def test_message_memory_types(self, store):
        """Test message memory types."""
        session = store.create_session(name="Test")
        msg = store.add_message(
            session_id=session.id,
            role="assistant",
            content="Test",
        )
        assert msg.memory_type == "working"


class TestSessionStore:
    """Tests for SessionStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a test store with SQLite."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()
        return store

    def test_create_session(self, store):
        """Test creating a session."""
        session = store.create_session(name="Test Session", user_id="user-123")
        assert session.name == "Test Session"
        assert session.user_id == "user-123"
        assert session.id is not None

    def test_get_session(self, store):
        """Test getting a session by ID."""
        created = store.create_session(name="Test Session")
        retrieved = store.get_session(created.id)
        assert retrieved.id == created.id
        assert retrieved.name == "Test Session"

    def test_get_session_not_found(self, store):
        """Test getting non-existent session returns None."""
        result = store.get_session(uuid.uuid4())
        assert result is None

    def test_list_sessions(self, store):
        """Test listing sessions."""
        store.create_session(name="Session 1", user_id="user-1")
        store.create_session(name="Session 2", user_id="user-1")
        store.create_session(name="Session 3", user_id="user-2")

        user1_sessions = store.list_sessions(user_id="user-1")
        assert len(user1_sessions) == 2

    def test_update_session(self, store):
        """Test updating a session."""
        session = store.create_session(name="Original Name")
        updated = store.update_session(session.id, name="Updated Name")
        assert updated.name == "Updated Name"

    def test_delete_session(self, store):
        """Test deleting a session."""
        session = store.create_session(name="To Delete")
        result = store.delete_session(session.id)
        assert result is True
        assert store.get_session(session.id) is None


class TestMessageOperations:
    """Tests for message operations."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a test store with SQLite."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()
        return store

    def test_add_message(self, store):
        """Test adding a message to a session."""
        session = store.create_session(name="Test")
        message = store.add_message(
            session_id=session.id,
            role="user",
            content="Hello",
        )
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.turn_index == 1

    def test_add_multiple_messages(self, store):
        """Test adding multiple messages increments turn_index."""
        session = store.create_session(name="Test")
        msg1 = store.add_message(session.id, "user", "Hello")
        msg2 = store.add_message(session.id, "assistant", "Hi there")
        msg3 = store.add_message(session.id, "user", "How are you?")

        assert msg1.turn_index == 1
        assert msg2.turn_index == 2
        assert msg3.turn_index == 3

    def test_get_messages(self, store):
        """Test getting messages from a session."""
        session = store.create_session(name="Test")
        store.add_message(session.id, "user", "Hello")
        store.add_message(session.id, "assistant", "Hi")

        messages = store.get_messages(session.id)
        assert len(messages) == 2

    def test_archive_message(self, store):
        """Test archiving a message."""
        session = store.create_session(name="Test")
        message = store.add_message(session.id, "user", "Hello")

        archived = store.archive_message(message.id)
        assert archived.is_archived is True


class TestContextRetrieval:
    """Tests for context retrieval methods."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a test store with SQLite."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        store.create_tables()
        return store

    def test_database_type_detection_sqlite(self, tmp_path):
        """Test database type detection for SQLite."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        assert store.is_sqlite is True
        assert store.is_postgresql is False

    def test_database_type_detection_postgresql(self):
        """Test database type detection for PostgreSQL."""
        store = SessionStore("postgresql://user:pass@localhost/tinycua")
        assert store.is_postgresql is True
        assert store.is_sqlite is False

    def test_pgvector_detection_no_pgvector(self, tmp_path):
        """Test pgvector detection when not installed."""
        db_path = tmp_path / "test.db"
        store = SessionStore(f"sqlite:///{db_path}")
        assert store.has_pgvector() is False

    def test_get_recent_turns(self, store):
        """Test getting recent turns."""
        session = store.create_session(name="Test")
        store.add_message(session.id, "user", "Hello")
        store.add_message(session.id, "assistant", "Hi")
        store.add_message(session.id, "user", "How are you?")
        store.add_message(session.id, "assistant", "Good")
        store.add_message(session.id, "user", "Great")

        recent = store.get_recent_turns(session.id, count=3)
        assert len(recent) == 3
        assert recent[0].content == "How are you?"
        assert recent[1].content == "Good"
        assert recent[2].content == "Great"

    def test_search_grep(self, store):
        """Test grep search in full context."""
        session = store.create_session(name="Test")
        store.add_message(session.id, "user", "My name is Bob")
        store.add_message(session.id, "assistant", "Hi Bob!")
        store.add_message(session.id, "user", "I like blue color")
        store.add_message(session.id, "assistant", "Blue is nice")

        store.update_full_context(session.id)

        results = store.search_grep(session.id, "Bob")
        assert len(results) == 1
        assert "Bob" in results[0]["content"]

        results = store.search_grep(session.id, "color")
        assert len(results) == 1
        assert "color" in results[0]["content"]

    def test_update_and_get_summary(self, store):
        """Test updating and getting summary."""
        session = store.create_session(name="Test")
        store.add_message(session.id, "user", "Hello")
        store.add_message(session.id, "assistant", "Hi")

        summary_text = "# Conversation Summary\n\nUser greeted the assistant."
        store.update_summary(session.id, summary_text)

        retrieved = store.get_summary(session.id)
        assert retrieved == summary_text

        session = store.get_session(session.id)
        assert session.has_summary is True
