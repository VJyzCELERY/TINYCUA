# Unit tests for Message Sanitizer


from tinycua_sdk.context.sanitizer import MessageSanitizer


class TestMessageSanitizer:
    """Tests for the MessageSanitizer class."""

    def test_sanitize_tool_call_basic(self):
        """Test basic tool call sanitization."""
        sanitizer = MessageSanitizer()

        tool_call = {
            "name": "test_tool",
            "arguments": '{"key": "value"}',
        }

        result = sanitizer.sanitize_tool_call(tool_call)

        assert result["name"] == "test_tool"
        assert "key" in result["arguments"]

    def test_sanitize_tool_call_with_control_chars(self):
        """Test removing control characters."""
        sanitizer = MessageSanitizer()

        tool_call = {
            "name": "test\x00tool",
            "arguments": '{"key": "value\x01"}',
        }

        result = sanitizer.sanitize_tool_call(tool_call)

        assert "\x00" not in result["name"]
        assert "\x01" not in result["arguments"]

    def test_sanitize_result(self):
        """Test result sanitization."""
        sanitizer = MessageSanitizer()

        result = {
            "content": "Test result\x00",
            "status": "success",
        }

        sanitized = sanitizer.sanitize_result(result)

        assert "\x00" not in sanitized["content"]

    def test_sanitize_system_prompt(self):
        """Test system prompt sanitization."""
        sanitizer = MessageSanitizer()

        prompt = "System prompt with {{template}} and <script>alert(1)</script>"

        result = sanitizer.sanitize_system_prompt(prompt)

        # Template should be escaped (not removed) - \{{ means escaped
        assert r"\{{" in result  # Template escaped
        assert "<script>" not in result  # HTML stripped

    def test_sanitize_message_basic(self):
        """Test message sanitization."""
        sanitizer = MessageSanitizer()

        message = {
            "role": "user",
            "content": "Hello world",
        }

        result = sanitizer.sanitize_message(message)

        assert result["role"] == "user"
        assert result["content"] == "Hello world"

    def test_sanitize_message_with_tool_calls(self):
        """Test message with tool calls."""
        sanitizer = MessageSanitizer()

        message = {
            "role": "assistant",
            "content": "I'll use the tool",
            "tool_calls": [
                {
                    "id": "call_123",
                    "name": "tool_name",
                    "arguments": '{"query": "test"}',
                }
            ],
        }

        result = sanitizer.sanitize_message(message)

        assert "tool_calls" in result

    def test_sanitize_tool_args_json(self):
        """Test sanitizing JSON tool arguments."""
        sanitizer = MessageSanitizer()

        args = '{"query": "test", "limit": 10}'

        result = sanitizer.sanitize_tool_args(args)

        # Should be valid JSON
        import json

        parsed = json.loads(result)
        assert parsed["query"] == "test"

    def test_sanitize_removes_html_tags(self):
        """Test HTML tag removal."""
        sanitizer = MessageSanitizer()

        content = "<div>Hello</div><script>alert(1)</script>"

        result = sanitizer._sanitize_string(content)

        assert "<div>" not in result
        assert "<script>" not in result
