"""Tests for TUI chat interface."""

import pytest


class TestChatInterface:
    """Test ChatInterface class."""

    def test_chat_interface_initializes(self):
        """Test chat interface initializes with empty state."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        assert chat._messages == []
        assert chat._input_history == []
        assert chat._history_index == -1

    def test_chat_interface_add_user_message(self):
        """Test adding user message."""
        from tinycua.tui.chat import ChatInterface, ChatMessage

        chat = ChatInterface()
        chat.add_user_message("Hello")
        
        assert len(chat._messages) == 1
        assert chat._messages[0].role == "user"
        assert chat._messages[0].content == "Hello"

    def test_chat_interface_add_assistant_message(self):
        """Test adding assistant message."""
        from tinycua.tui.chat import ChatInterface, ChatMessage

        chat = ChatInterface()
        chat.add_assistant_message("Hi there!")
        
        assert len(chat._messages) == 1
        assert chat._messages[0].role == "assistant"
        assert chat._messages[0].content == "Hi there!"

    def test_chat_interface_message_history(self):
        """Test message history is maintained."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        chat.add_user_message("First")
        chat.add_user_message("Second")
        
        assert len(chat._messages) == 2

    def test_chat_interface_add_to_input_history(self):
        """Test input is added to history."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        chat.add_to_input_history("Hello")
        chat.add_to_input_history("World")
        
        assert len(chat._input_history) == 2
        assert chat._input_history[0] == "Hello"

    def test_chat_interface_history_navigation(self):
        """Test navigating input history."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        chat.add_to_input_history("First")
        chat.add_to_input_history("Second")
        chat.add_to_input_history("Third")
        chat._history_index = 2
        
        result = chat.get_previous_input()
        assert result == "Second"
        
        result = chat.get_previous_input()
        assert result == "First"
        
        result = chat.get_next_input()
        assert result == "Second"

    def test_chat_interface_get_formatted_messages(self):
        """Test getting formatted message display."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        chat.add_user_message("Hello")
        chat.add_assistant_message("Hi there!")
        
        formatted = chat.get_formatted_messages()
        assert "You>" in formatted
        assert "Assistant>" in formatted

    def test_chat_interface_clear(self):
        """Test clearing chat messages."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        chat.add_user_message("Hello")
        chat.add_assistant_message("Hi")
        chat.clear()
        
        assert chat._messages == []

    def test_chat_interface_stream_response(self):
        """Test streaming response addition."""
        from tinycua.tui.chat import ChatInterface

        chat = ChatInterface()
        chat.start_streaming()
        chat.append_stream_chunk("Hello")
        chat.append_stream_chunk(" World")
        result = chat.finalize_stream()
        
        assert len(chat._messages) == 1
        assert chat._messages[0].content == "Hello World"
        assert result == "Hello World"
