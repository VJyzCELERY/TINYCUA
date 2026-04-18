"""Integration Tests: Agent Context Tools

Tests based on example: 06_local_storage.py
Tests:
1. Session store creation
2. Message management
3. Context retrieval tools
4. Context search functionality
"""

import pytest
import tempfile
import logging
from pathlib import Path
from tinycua_sdk.storage.store import SessionStore
from tinycua.agent.tools.context_tools import (
    get_context_summary_tool,
    get_recent_turns_tool,
    search_context_grep_tool,
)

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_store():
    """Create a temporary session store."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "tinycua.db"
    db_url = f"sqlite:///{db_path}"

    store = SessionStore(db_url)
    store.create_tables()

    yield store

    import shutil
    shutil.rmtree(temp_dir)


# =============================================================================
# Test Cases
# =============================================================================

class TestSessionStore:
    """Test session store functionality."""

    def test_create_store(self, temp_store):
        """Test creating a session store."""
        assert temp_store is not None
        assert temp_store.db_url is not None

    def test_create_tables(self, temp_store):
        """Test creating tables."""
        logger.info("Testing create_tables")
        temp_store.create_tables()
        logger.info("Tables created successfully")

    def test_create_session(self, temp_store):
        """Test creating a session."""
        logger.info("Testing create_session")
        session = temp_store.create_session(
            name="Test Session", user_id="user-123"
        )
        logger.info(f"Session created: {session.id}")
        assert session.id is not None
        assert session.name == "Test Session"
        assert session.user_id == "user-123"

    def test_add_message(self, temp_store):
        """Test adding a message."""
        logger.info("Testing add_message")
        session = temp_store.create_session(name="Test Session")
        message = temp_store.add_message(session.id, "user", "Hello")
        logger.info(f"Message added: {message.id}")
        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Hello"


class TestContextRetrievalTools:
    """Test context retrieval tools."""

    def test_get_context_summary_tool(self, temp_store):
        """Test creating context summary tool."""
        logger.info("Testing get_context_summary_tool")
        session = temp_store.create_session(name="Test Session")

        tool = get_context_summary_tool(temp_store, session.id)
        logger.info(f"Created summary tool: {tool.name}")
        assert tool is not None

    def test_get_recent_turns_tool(self, temp_store):
        """Test creating recent turns tool."""
        logger.info("Testing get_recent_turns_tool")
        session = temp_store.create_session(name="Test Session")

        tool = get_recent_turns_tool(temp_store, session.id)
        logger.info(f"Created recent turns tool: {tool.name}")
        assert tool is not None

    def test_search_context_grep_tool(self, temp_store):
        """Test creating grep search tool."""
        logger.info("Testing search_context_grep_tool")
        session = temp_store.create_session(name="Test Session")

        tool = search_context_grep_tool(temp_store, session.id)
        logger.info(f"Created grep tool: {tool.name}")
        assert tool is not None

    def test_search_context_grep_tool_empty(self, temp_store):
        """Test grep search with empty context."""
        logger.info("Testing grep with empty context")
        session = temp_store.create_session(name="Test Session")

        tool = search_context_grep_tool(temp_store, session.id)

        # Execute tool with empty context
        result = tool.invoke(query="test")
        logger.info(f"Grep result: {result}")
        assert isinstance(result, dict)


class TestMessageManagement:
    """Test message management."""

    def test_update_full_context(self, temp_store):
        """Test updating full context for search."""
        session = temp_store.create_session(name="Test Session")

        # Add some messages
        temp_store.add_message(session.id, "user", "Hello")
        temp_store.add_message(session.id, "assistant", "Hi there!")

        # Update full context
        temp_store.update_full_context(session.id)
        # If no exception, update was successful

    def test_update_summary(self, temp_store):
        """Test updating session summary."""
        session = temp_store.create_session(name="Test Session")

        summary = "# Test Summary\n\nThis is a test."
        temp_store.update_summary(session.id, summary)
        # If no exception, summary was updated


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
