"""Context compression for large window management."""

from typing import Any, Callable

from tinycua_sdk.storage.models import Message


class CompressionError(Exception):
    """Raised when context compression fails."""

    pass


class ContextCompressor:
    """Compresses context for large window management.

    Supports sliding window and summarization strategies for
    managing large context windows (8K-32K tokens).
    """

    def __init__(
        self,
        window_size: int = 8000,
        token_counter: Callable[[str], int] | None = None,
    ):
        """Initialize compressor.

        Args:
            window_size: Target window size in tokens
            token_counter: Optional custom token counter
        """
        self.window_size = window_size
        self.token_counter = token_counter or self._default_token_counter

    def _default_token_counter(self, text: str) -> int:
        """Default token counter using character approximation.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        # Rough approximation: 4 characters per token
        return len(text) // 4

    def compress(
        self,
        messages: list[Message],
        strategy: str = "sliding",
    ) -> list[Message]:
        """Compress messages using specified strategy.

        Args:
            messages: List of Message objects to compress
            strategy: Compression strategy ("sliding" or "summarize")

        Returns:
            Compressed message list

        Raises:
            CompressionError: If compression fails
        """
        # Validate strategy first before processing
        if strategy not in ("sliding", "summarize"):
            raise CompressionError(f"Unknown strategy: {strategy}")

        if not messages:
            return []

        if strategy == "sliding":
            return self.sliding_window(messages)
        else:  # summarize
            return self.summarize(messages)

    def sliding_window(
        self,
        messages: list[Message],
        keep_recent: int = 5,
    ) -> list[Message]:
        """Keep only recent N turns.

        Args:
            messages: List of Message objects
            keep_recent: Number of recent turns to keep

        Returns:
            Filtered message list
        """
        if not messages:
            return []

        # Group by turn_index
        turns: dict[int, list[Message]] = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        # Get recent turns
        sorted_turns = sorted(turns.keys(), reverse=True)
        recent_turns = sorted_turns[:keep_recent]

        # Collect messages from recent turns
        result = []
        for turn in recent_turns:
            result.extend(turns[turn])

        # Sort by original order
        result.sort(key=lambda m: (m.turn_index, m.created_at or 0))

        return result

    def summarize(
        self,
        messages: list[Message],
        llm_client: Any = None,
        summary_length: int = 500,
    ) -> list[Message]:
        """Summarize older messages into compact form using LLM.

        Args:
            messages: List of Message objects to summarize
            llm_client: Optional LLM client for summarization
            summary_length: Target summary length in tokens

        Returns:
            Messages with older content summarized

        Note:
            If llm_client is None, falls back to sliding window strategy.
        """
        if not messages:
            return []

        # If no LLM client, fall back to sliding window
        if llm_client is None:
            return self.sliding_window(messages, keep_recent=10)

        # Validate client has required interface
        if not hasattr(llm_client, "chat"):
            return self.sliding_window(messages, keep_recent=10)

        # Separate recent and older messages
        recent_threshold = max(m.turn_index for m in messages) - 5
        recent = [m for m in messages if m.turn_index > recent_threshold]
        older = [m for m in messages if m.turn_index <= recent_threshold]

        if not older:
            return messages

        # Build summary prompt
        older_content = "\n".join(
            f"{m.role}: {m.content[:200]}..."
            if len(m.content) > 200
            else f"{m.role}: {m.content}"
            for m in older
        )

        prompt = (
            f"Summarize the following conversation concisely, preserving key "
            f"information:\n\n{older_content}"
        )

        try:
            # Call LLM for summarization
            response = llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=summary_length,
            )

            summary = response.choices[0].message.content

            # Create summary message - convert UUID to string if needed
            msg_id = older[0].id
            if hasattr(msg_id, "hex"):  # It's a UUID
                msg_id = str(msg_id)

            summary_msg = Message(
                id=msg_id,
                session_id=older[0].session_id,
                role="system",
                content=f"[Summary of previous conversation]\n{summary}",
                turn_index=recent[0].turn_index if recent else 0,
            )

            return [summary_msg] + recent

        except Exception:
            # Fall back to sliding window on error
            return self.sliding_window(messages)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        return self.token_counter(text)

    def estimate_message_tokens(self, message: Message) -> int:
        """Estimate token count for a message.

        Args:
            message: Message to estimate

        Returns:
            Estimated token count
        """
        content = message.content or ""
        reasoning = message.reasoning or ""
        return self.count_tokens(content) + self.count_tokens(reasoning)
