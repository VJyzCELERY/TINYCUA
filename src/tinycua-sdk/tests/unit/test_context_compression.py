# Unit tests for Context Compression

import pytest
from datetime import datetime

from tinycua_sdk.context.compression import ContextCompressor, CompressionError
from tinycua_sdk.storage.models import Message
import uuid


def create_message(role: str, content: str, turn_index: int = 0) -> Message:
    """Helper to create a test message."""
    return Message(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        role=role,
        content=content,
        turn_index=turn_index,
        created_at=datetime.now(),
    )


class TestContextCompressor:
    """Tests for the ContextCompressor class."""

    def test_sliding_window_basic(self):
        """Test sliding window keeps recent turns."""
        messages = [
            create_message("user", "Hello", turn_index=0),
            create_message("assistant", "Hi", turn_index=0),
            create_message("user", "How are you?", turn_index=1),
            create_message("assistant", "Good", turn_index=1),
        ]

        compressor = ContextCompressor()
        result = compressor.sliding_window(messages, keep_recent=1)

        # Should only keep turn 1
        assert all(m.turn_index == 1 for m in result)
        assert len(result) == 2

    def test_sliding_window_empty(self):
        """Test sliding window with empty messages."""
        compressor = ContextCompressor()
        result = compressor.sliding_window([])

        assert result == []

    def test_compress_sliding_strategy(self):
        """Test compress with sliding strategy."""
        messages = [
            create_message("user", "Hello", turn_index=0),
            create_message("assistant", "Hi", turn_index=1),
        ]

        compressor = ContextCompressor()
        result = compressor.compress(messages, strategy="sliding")

        assert len(result) > 0

    def test_compress_summarize_fallback(self):
        """Test summarize falls back to sliding when no LLM."""
        messages = [
            create_message("user", "Hello", turn_index=0),
            create_message("assistant", "Hi", turn_index=1),
        ]

        compressor = ContextCompressor()
        result = compressor.compress(messages, strategy="summarize")

        # Should fall back to sliding window
        assert len(result) > 0

    def test_compress_invalid_strategy(self):
        """Test compress with invalid strategy raises error."""
        compressor = ContextCompressor()

        with pytest.raises(CompressionError, match="Unknown strategy"):
            compressor.compress([], strategy="invalid")

    def test_token_counter_default(self):
        """Test default token counter."""
        compressor = ContextCompressor()

        # 8 chars / 4 = 2 tokens
        count = compressor.count_tokens("12345678")

        assert count == 2

    def test_estimate_message_tokens(self):
        """Test estimating tokens for a message."""
        msg = create_message("user", "Hello world", turn_index=0)

        compressor = ContextCompressor()
        tokens = compressor.estimate_message_tokens(msg)

        assert tokens > 0
