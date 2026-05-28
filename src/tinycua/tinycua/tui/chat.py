"""Chat interface for TinyCUA TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MessageRole = Literal["user", "assistant", "tool"]


@dataclass
class ChatMessage:
    """Represents a chat message.

    Attributes:
        role: Message role (user/assistant/tool).
        content: Message content.
        timestamp: Optional timestamp.
    """

    role: MessageRole
    content: str
    timestamp: str | None = None


class ChatInterface:
    """Chat interface with message history and input tracking.

    Manages chat messages, input history navigation, and
    response streaming for the TUI.
    """

    def __init__(self) -> None:
        """Initialize the chat interface."""
        self._messages: list[ChatMessage] = []
        self._input_history: list[str] = []
        self._history_index: int = -1
        self._streaming_buffer: str = ""
        self._is_streaming: bool = False

    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat.

        Args:
            content: Message text.
        """
        msg = ChatMessage(role="user", content=content)
        self._messages.append(msg)
        self.add_to_input_history(content)

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the chat.

        Args:
            content: Message text.
        """
        msg = ChatMessage(role="assistant", content=content)
        self._messages.append(msg)

    def add_tool_message(self, content: str) -> None:
        """Add a tool message to the chat.

        Args:
            content: Tool output text.
        """
        msg = ChatMessage(role="tool", content=content)
        self._messages.append(msg)

    def add_to_input_history(self, text: str) -> None:
        """Add text to input history.

        Args:
            text: Input text to remember.
        """
        if text and (not self._input_history or self._input_history[-1] != text):
            self._input_history.append(text)
        self._history_index = len(self._input_history)

    def get_previous_input(self) -> str | None:
        """Navigate to previous input in history.

        Returns:
            Previous input or None if at start.
        """
        if not self._input_history:
            return None
        if self._history_index > 0:
            self._history_index -= 1
        return self._input_history[self._history_index]

    def get_next_input(self) -> str | None:
        """Navigate to next input in history.

        Returns:
            Next input or None if at end.
        """
        if not self._input_history:
            return None
        if self._history_index < len(self._input_history) - 1:
            self._history_index += 1
            return self._input_history[self._history_index]
        self._history_index = len(self._input_history)
        return ""

    def get_formatted_messages(self) -> str:
        """Get formatted messages for display.

        Returns:
            Formatted message string.
        """
        lines = []
        for msg in self._messages:
            if msg.role == "user":
                lines.append(f"[bold blue]You>[/bold blue] {msg.content}")
            elif msg.role == "assistant":
                lines.append(f"[green]Assistant>[/green] {msg.content}")
            else:
                lines.append(f"[dim]Tool>[/dim] {msg.content}")
        return "\n".join(lines)

    def get_messages(self) -> list[ChatMessage]:
        """Get all chat messages.

        Returns:
            List of chat messages.
        """
        return self._messages.copy()

    def clear(self) -> None:
        """Clear all chat messages."""
        self._messages = []

    def start_streaming(self) -> None:
        """Start streaming a response."""
        self._is_streaming = True
        self._streaming_buffer = ""

    def append_stream_chunk(self, chunk: str) -> None:
        """Append a chunk to streaming response.

        Args:
            chunk: Text chunk to append.
        """
        if self._is_streaming:
            self._streaming_buffer += chunk

    def finalize_stream(self) -> str:
        """Finalize streaming and add as assistant message.

        Returns:
            The complete streamed content.
        """
        if self._is_streaming and self._streaming_buffer:
            self.add_assistant_message(self._streaming_buffer)
        self._is_streaming = False
        result = self._streaming_buffer
        self._streaming_buffer = ""
        return result

    def is_streaming(self) -> bool:
        """Check if currently streaming.

        Returns:
            True if streaming.
        """
        return self._is_streaming
