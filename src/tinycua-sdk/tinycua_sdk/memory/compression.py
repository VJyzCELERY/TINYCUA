"""Context compression using summarization for token limit management."""

import logging
from typing import Any, Callable


logger = logging.getLogger(__name__)


class ContextCompressor:
    """Compresses conversation context using summarization."""

    def __init__(
        self,
        token_threshold: int = 50000,
        compression_ratio: float = 0.5,
        summarize_fn: Callable[[list[dict[str, Any]]], str] | None = None,
    ):
        """Initialize context compressor.

        Args:
            token_threshold: Token count to trigger compression
            compression_ratio: Target compression ratio (0.0-1.0)
            summarize_fn: Optional custom summarization function

        """
        self._token_threshold = token_threshold
        self._compression_ratio = compression_ratio
        self._summarize_fn = summarize_fn

    def should_compress(self, messages: list[dict[str, Any]]) -> bool:
        """Check if compression is needed.

        Args:
            messages: List of messages to check

        Returns:
            True if compression is needed

        """
        total_tokens = self._estimate_total_tokens(messages)
        return total_tokens > self._token_threshold

    def compress(
        self,
        messages: list[dict[str, Any]],
        strategy: str = "summarize",
    ) -> list[dict[str, Any]]:
        """Compress messages to fit within token limit.

        Args:
            messages: List of messages to compress
            strategy: Compression strategy ('summarize', 'truncate', 'window')

        Returns:
            Compressed list of messages

        """
        target_tokens = int(self._token_threshold * self._compression_ratio)
        current_tokens = self._estimate_total_tokens(messages)

        if current_tokens <= target_tokens:
            return messages

        if strategy == "summarize":
            return self._compress_summarize(messages, target_tokens)
        elif strategy == "truncate":
            return self._compress_truncate(messages, target_tokens)
        elif strategy == "window":
            return self._compress_window(messages, target_tokens)
        else:
            return self._compress_summarize(messages, target_tokens)

    def _compress_summarize(
        self,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> list[dict[str, Any]]:
        """Compress using summarization.

        Args:
            messages: Messages to compress
            target_tokens: Target token count

        Returns:
            Compressed messages with summary

        """
        if self._summarize_fn:
            summary = self._summarize_fn(messages)
            return [
                {
                    "role": "system",
                    "content": f"[Previous conversation summary: {summary}]",
                    "metadata": {"compressed": True},
                }
            ]

        summary_text = self._generate_summary(messages)
        return [
            {
                "role": "system",
                "content": f"[Previous conversation summary: {summary_text}]",
                "metadata": {"compressed": True},
            }
        ]

    def _compress_truncate(
        self,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> list[dict[str, Any]]:
        """Compress by keeping most recent messages.

        Args:
            messages: Messages to compress
            target_tokens: Target token count

        Returns:
            Truncated messages

        """
        result: list[dict[str, Any]] = []
        total_tokens = 0

        for msg in reversed(messages):
            tokens = self._estimate_tokens(msg.get("content", ""))
            if total_tokens + tokens > target_tokens:
                break
            result.insert(0, msg)
            total_tokens += tokens

        return result

    def _compress_window(
        self,
        messages: list[dict[str, Any]],
        target_tokens: int,
    ) -> list[dict[str, Any]]:
        """Compress using sliding window (keeps first + recent).

        Args:
            messages: Messages to compress
            target_tokens: Target token count

        Returns:
            Messages with sliding window

        """
        if len(messages) <= 2:
            return messages

        window_size = len(messages) // 2
        recent = messages[-window_size:]

        return messages[:1] + recent

    def _generate_summary(self, messages: list[dict[str, Any]]) -> str:
        """Generate a summary of messages using extractive method.

        Args:
            messages: Messages to summarize

        Returns:
            Summary string

        """
        if not messages:
            return "Empty conversation"

        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "just", "and", "but", "if", "or", "because", "until",
            "while", "this", "that", "these", "those", "it", "its", "i", "you",
            "we", "they", "he", "she", "me", "him", "her", "us", "them", "my",
            "your", "our", "their", "what", "which", "who", "whom", "about",
        }

        word_freq: dict[str, int] = {}
        for msg in messages:
            content = msg.get("content", "").lower()
            words = content.split()
            for word in words:
                clean_word = "".join(c for c in word if c.isalnum())
                if clean_word and clean_word not in stop_words and len(clean_word) > 2:
                    word_freq[clean_word] = word_freq.get(clean_word, 0) + 1

        top_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        topic_list = ", ".join(word for word, _ in top_topics)

        first_msg = messages[0].get("content", "")[:100]
        last_msg = messages[-1].get("content", "")[:100] if len(messages) > 1 else ""

        summary_parts = [f"{len(messages)} messages"]
        if topic_list:
            summary_parts.append(f"topics: {topic_list}")
        if first_msg:
            summary_parts.append(f"started with: {first_msg}...")
        if last_msg:
            summary_parts.append(f"ended with: {last_msg}...")

        return "; ".join(summary_parts)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count

        """
        return max(1, len(text) // 4)

    def _estimate_total_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate total tokens in messages.

        Args:
            messages: Messages to estimate

        Returns:
            Total estimated tokens

        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += self._estimate_tokens(content)
        return total


__all__ = ["ContextCompressor"]
