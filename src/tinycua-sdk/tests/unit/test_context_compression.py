import pytest
from tinycua_sdk.memory.compression import ContextCompressor


class TestContextCompressor:
    """Test ContextCompressor class."""

    def test_initialization(self):
        """Test initializing compressor."""
        comp = ContextCompressor(token_threshold=1000, compression_ratio=0.5)
        assert comp._token_threshold == 1000
        assert comp._compression_ratio == 0.5

    def test_should_compress_false(self):
        """Test should_compress returns False when under threshold."""
        comp = ContextCompressor(token_threshold=1000)
        messages = [{"content": "Short message"}]
        assert comp.should_compress(messages) is False

    def test_should_compress_true(self):
        """Test should_compress returns True when over threshold."""
        comp = ContextCompressor(token_threshold=10)
        messages = [{"content": "A" * 100}]
        assert comp.should_compress(messages) is True

    def test_compress_below_threshold(self):
        """Test compression does nothing when under threshold."""
        comp = ContextCompressor(token_threshold=1000)
        messages = [{"content": "Short message"}]
        result = comp.compress(messages)
        assert result == messages

    def test_compress_summarize_strategy(self):
        """Test summarize compression strategy."""
        comp = ContextCompressor(
            token_threshold=10,
            compression_ratio=0.5,
        )
        messages = [
            {"role": "user", "content": "Hello " * 10},
            {"role": "assistant", "content": "Hi there " * 10},
        ]
        result = comp.compress(messages, strategy="summarize")
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert "summary" in result[0]["content"].lower()
        assert result[0].get("metadata", {}).get("compressed") is True

    def test_compress_truncate_strategy(self):
        """Test truncate compression strategy."""
        comp = ContextCompressor(
            token_threshold=10,
            compression_ratio=0.5,
        )
        messages = [
            {"role": "user", "content": "A" * 50},
            {"role": "assistant", "content": "B" * 50},
        ]
        result = comp.compress(messages, strategy="truncate")
        total_tokens = sum(len(m["content"]) // 4 for m in result)
        assert total_tokens <= 10

    def test_compress_window_strategy(self):
        """Test window compression strategy."""
        comp = ContextCompressor(
            token_threshold=10,
            compression_ratio=0.5,
        )
        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Message 2"},
            {"role": "user", "content": "Message 3"},
            {"role": "assistant", "content": "Message 4"},
        ]
        result = comp.compress(messages, strategy="window")
        assert len(result) < len(messages)

    def test_custom_summarize_function(self):
        """Test custom summarization function."""
        def custom_summarize(messages):
            return f"Custom summary of {len(messages)} messages"

        comp = ContextCompressor(
            token_threshold=5,
            summarize_fn=custom_summarize,
        )
        messages = [{"content": "Test " * 20}]
        result = comp.compress(messages, strategy="summarize")
        assert "Custom summary" in result[0]["content"]

    def test_estimate_tokens(self):
        """Test token estimation."""
        comp = ContextCompressor()
        tokens = comp._estimate_tokens("Hello world")
        assert tokens >= 2

    def test_estimate_total_tokens(self):
        """Test total token estimation."""
        comp = ContextCompressor()
        messages = [
            {"content": "Hello"},
            {"content": "World"},
        ]
        total = comp._estimate_total_tokens(messages)
        assert total >= 2