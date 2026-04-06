"""Message sanitization for tool calls."""

import json
import re
from typing import Any


class SanitizationError(Exception):
    """Raised when sanitization fails."""

    pass


class MessageSanitizer:
    """Sanitizes tool calls and results.

    Provides pre-call sanitization for tool calls to ensure message integrity.
    Removes or escapes dangerous content before sending to LLM.
    """

    # Control characters to remove
    CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

    # HTML-like tags to strip
    HTML_TAGS = re.compile(r"</?[a-zA-Z][^>]*>", re.IGNORECASE)

    # Template syntax to escape
    TEMPLATE_SYNTAX = re.compile(r"\{\{.*?\}\}")

    # Potentially dangerous patterns
    DANGEROUS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
    ]

    def sanitize_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Sanitize a tool call before execution.

        Args:
            tool_call: Raw tool call dict

        Returns:
            Sanitized tool call

        Raises:
            SanitizationError: If sanitization fails
        """
        try:
            sanitized = {}

            # Sanitize tool name
            if "name" in tool_call:
                sanitized["name"] = self._sanitize_string(tool_call["name"])

            # Sanitize arguments
            if "arguments" in tool_call:
                args = tool_call["arguments"]
                if isinstance(args, str):
                    sanitized["arguments"] = self.sanitize_tool_args(args)
                elif isinstance(args, dict):
                    sanitized["arguments"] = self._sanitize_dict(args)
                else:
                    sanitized["arguments"] = args

            # Preserve ID if present
            if "id" in tool_call:
                sanitized["id"] = tool_call["id"]

            return sanitized

        except Exception as e:
            raise SanitizationError(f"Failed to sanitize tool call: {e}")

    def sanitize_tool_args(self, args: str) -> str:
        """Sanitize tool arguments string.

        Args:
            args: Arguments as JSON string

        Returns:
            Sanitized arguments
        """
        try:
            # Try to parse and re-serialize for clean output
            parsed = json.loads(args)
            sanitized = self._sanitize_dict(parsed)
            return json.dumps(sanitized, ensure_ascii=False)
        except json.JSONDecodeError:
            # If not valid JSON, sanitize as string
            return self._sanitize_string(args)

    def sanitize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Sanitize a tool result before returning.

        Args:
            result: Raw tool result

        Returns:
            Sanitized result
        """
        return self._sanitize_dict(result)

    def sanitize_system_prompt(self, prompt: str) -> str:
        """Sanitize system prompt before sending to LLM.

        Args:
            prompt: Raw system prompt

        Returns:
            Sanitized system prompt
        """
        # Remove control characters
        prompt = self.CONTROL_CHARS.sub("", prompt)

        # Escape template syntax
        prompt = self.TEMPLATE_SYNTAX.sub(lambda m: "\\" + m.group(0), prompt)

        # Strip dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            prompt = pattern.sub("", prompt)

        return prompt.strip()

    def sanitize_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Sanitize agent message before sending to LLM.

        Args:
            message: Raw message dict

        Returns:
            Sanitized message
        """
        sanitized = {}

        # Sanitize role
        if "role" in message:
            sanitized["role"] = self._sanitize_string(message["role"])

        # Sanitize content
        if "content" in message and message["content"]:
            content = message["content"]
            if isinstance(content, str):
                sanitized["content"] = self._sanitize_string(content)
            elif isinstance(content, list):
                sanitized["content"] = [
                    self._sanitize_content_block(block) for block in content
                ]
            else:
                sanitized["content"] = content

        # Preserve other fields
        for key in ["name", "tool_calls", "tool_call_id"]:
            if key in message:
                sanitized[key] = message[key]

        return sanitized

    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string value.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        if not isinstance(text, str):
            return text

        # Remove control characters
        text = self.CONTROL_CHARS.sub("", text)

        # Escape template syntax
        text = self.TEMPLATE_SYNTAX.sub(lambda m: "\\" + m.group(0), text)

        # Strip HTML tags
        text = self.HTML_TAGS.sub("", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize dictionary values.

        Args:
            data: Dictionary to sanitize

        Returns:
            Sanitized dictionary
        """
        sanitized = {}

        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_dict(item)
                    if isinstance(item, dict)
                    else self._sanitize_string(item)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_content_block(self, block: dict[str, Any]) -> dict[str, Any]:
        """Sanitize a content block (for multi-part messages).

        Args:
            block: Content block

        Returns:
            Sanitized block
        """
        if not isinstance(block, dict):
            return block

        sanitized = {}

        for key, value in block.items():
            if key == "text" and isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif key in ["type", "source"]:
                sanitized[key] = value
            else:
                sanitized[key] = value

        return sanitized
