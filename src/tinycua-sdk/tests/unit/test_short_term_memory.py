import pytest
import threading
import time
from tinycua_sdk.memory.short_term import Message, ShortTermMemory


class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.metadata == {}

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert "timestamp" in d

    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        data = {"role": "user", "content": "Hello", "metadata": {}}
        msg = Message.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestShortTermMemory:
    """Test ShortTermMemory class."""

    def test_initialization(self):
        """Test initializing short-term memory."""
        mem = ShortTermMemory(session_id="test-session")
        assert mem.session_id == "test-session"
        assert len(mem) == 0

    def test_set_session_id(self):
        """Test setting session ID."""
        mem = ShortTermMemory()
        mem.set_session_id("new-session")
        assert mem.session_id == "new-session"
        assert len(mem) == 0

    def test_add_message(self):
        """Test adding messages."""
        mem = ShortTermMemory()
        mem.add("user", "Hello")
        mem.add("assistant", "Hi there")
        assert len(mem) == 2

    def test_message_window_limit(self):
        """Test message window limit."""
        mem = ShortTermMemory(message_window=3)
        for i in range(5):
            mem.add("user", f"Message {i}")
        assert len(mem) == 3

    def test_get_all(self):
        """Test getting all messages."""
        mem = ShortTermMemory()
        mem.add("user", "Hello")
        mem.add("assistant", "Hi")
        msgs = mem.get_all()
        assert len(msgs) == 2
        assert msgs[0]["content"] == "Hello"

    def test_get_context_token_limit(self):
        """Test context retrieval with token limit."""
        mem = ShortTermMemory(max_tokens=50)
        mem.add("user", "A" * 100)
        mem.add("assistant", "B" * 50)
        context = mem.get_context(max_tokens=30)
        total_tokens = sum(len(m["content"]) // 4 for m in context)
        assert total_tokens <= 30

    def test_clear(self):
        """Test clearing messages."""
        mem = ShortTermMemory()
        mem.add("user", "Hello")
        mem.clear()
        assert len(mem) == 0

    def test_estimate_tokens(self):
        """Test token estimation."""
        mem = ShortTermMemory()
        tokens = mem._estimate_tokens("Hello world")
        assert tokens >= 2


class TestShortTermMemoryThreadSafety:
    """Test thread safety of ShortTermMemory."""

    def test_concurrent_add(self):
        """Test concurrent message addition."""
        mem = ShortTermMemory(message_window=600)
        errors = []

        def add_messages():
            try:
                for _ in range(100):
                    mem.add("user", "test message")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_messages) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mem) == 500

    def test_concurrent_read_write(self):
        """Test concurrent read and write."""
        mem = ShortTermMemory()
        errors = []

        def writer():
            try:
                for i in range(50):
                    mem.add("user", f"message {i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    _ = mem.get_all()
                    _ = mem.get_context()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(2)]
        threads += [threading.Thread(target=reader) for _ in range(2)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0