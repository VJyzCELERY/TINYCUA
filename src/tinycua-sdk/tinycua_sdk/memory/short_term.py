"""Short-term memory management for session-based conversation context."""

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any


@dataclass
class Message:
    """Represents a single message in the conversation history."""

    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
        )


class ShortTermMemory:
    """Manages short-term conversation context within a session."""

    def __init__(
        self,
        session_id: str | None = None,
        message_window: int = 100,
        max_tokens: int = 100000,
    ):
        """Initialize short-term memory.

        Args:
            session_id: Optional session identifier
            message_window: Maximum number of messages to retain
            max_tokens: Maximum tokens in context window

        """
        self._session_id = session_id or "default"
        self._message_window = message_window
        self._max_tokens = max_tokens
        self._messages: list[Message] = []
        self._lock = RLock()

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID.

        Args:
            session_id: New session identifier

        """
        with self._lock:
            self._session_id = session_id
            self._messages.clear()

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        with self._lock:
            return self._session_id

    def add(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a message to the conversation history.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata

        """
        with self._lock:
            msg = Message(
                role=role,
                content=content,
                metadata=metadata or {},
            )
            self._messages.append(msg)

            if len(self._messages) > self._message_window:
                self._messages.pop(0)

    def get_all(self) -> list[dict[str, Any]]:
        """Get all messages as dictionaries.

        Returns:
            List of message dictionaries

        """
        with self._lock:
            return [msg.to_dict() for msg in self._messages]

    def get_context(self, max_tokens: int | None = None) -> list[dict[str, Any]]:
        """Get messages within token limit.

        Args:
            max_tokens: Maximum tokens (defaults to _max_tokens)

        Returns:
            List of messages within token limit

        """
        with self._lock:
            limit = max_tokens or self._max_tokens
            result: list[dict[str, Any]] = []
            total_tokens = 0

            for msg in reversed(self._messages):
                tokens = self._estimate_tokens(msg.content)
                if total_tokens + tokens > limit and result:
                    break
                result.insert(0, msg.to_dict())
                total_tokens += tokens

            return result

    def clear(self) -> None:
        """Clear all messages."""
        with self._lock:
            self._messages.clear()

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses conservative 4 chars per token estimation.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count

        """
        return max(1, len(text) // 4)

    def __len__(self) -> int:
        """Get number of messages."""
        with self._lock:
            return len(self._messages)


__all__ = ["Message", "ShortTermMemory"]
