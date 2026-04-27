"""Prompt injection detection."""

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class InjectionThreat:
    """Represents a detected injection threat."""

    pattern: str
    location: str
    matched_text: str
    severity: str = "medium"


class InjectionDetector:
    """Detects prompt injection attempts.

    Scans context files and memory for known injection patterns.
    Detected threats are logged but not automatically blocked.
    """

    # Common injection patterns (more specific patterns first)
    INJECTION_PATTERNS = [
        (
            re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
            "high",
        ),
        (
            re.compile(r"ignore\s+(previous|all|above)\s+instructions", re.IGNORECASE),
            "high",
        ),
        (re.compile(r"(system|admin)\s+mode", re.IGNORECASE), "high"),
        (re.compile(r"you\s+are\s+(now|acting\s+as)", re.IGNORECASE), "medium"),
        # Script tags before generic HTML to ensure high severity
        (re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL), "high"),
        (re.compile(r"javascript:", re.IGNORECASE), "high"),
        (re.compile(r"on\w+\s*=", re.IGNORECASE), "high"),
        (re.compile(r"<\/?[a-z]+[^>]*>", re.IGNORECASE), "medium"),  # HTML-like tags
        (re.compile(r"\{\{.*\}\}"), "medium"),  # Template injection
        (re.compile(r"\{\%\s*\w+\s*\%\}"), "medium"),  # Jinja-like templates
        (re.compile(r"\$\{.*\}"), "low"),  # Template literals
    ]

    def __init__(self, whitelist: list[str] | None = None):
        """Initialize with optional whitelist.

        Args:
            whitelist: Patterns to allow even if they match
        """
        self.whitelist = whitelist or []
        self._whitelist_patterns = [re.compile(p) for p in self.whitelist]

    def scan_text(self, text: str, location: str = "text") -> list[InjectionThreat]:
        """Scan text for injection patterns.

        Args:
            text: Text to scan
            location: Location identifier for reporting

        Returns:
            List of detected threats with location and pattern
        """
        threats = []

        # Check against whitelist first
        for wp in self._whitelist_patterns:
            if wp.search(text):
                return []  # Whitelisted

        # Check against injection patterns
        for pattern, severity in self.INJECTION_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                threats.append(
                    InjectionThreat(
                        pattern=pattern.pattern,
                        location=location,
                        matched_text=match.group(0)[:100],  # Truncate for reporting
                        severity=severity,
                    )
                )

        return threats

    def scan_file(self, path: Path) -> list[InjectionThreat]:
        """Scan a file for injection patterns.

        Args:
            path: File path to scan

        Returns:
            List of detected threats
        """
        if not path.exists() or not path.is_file():
            return []

        try:
            content = path.read_text(encoding="utf-8")
            return self.scan_text(content, location=str(path))
        except OSError:
            return []

    def scan_memory(self, session_id: uuid.UUID) -> list[InjectionThreat]:
        """Scan memory for injection patterns.

        Args:
            session_id: Session ID to scan

        Returns:
            List of detected threats
        """
        threats = []

        try:
            from tinycua_sdk.storage.store import get_session_store

            store = get_session_store()
            messages = store.list_messages(session_id)

            for msg in messages:
                content = msg.content or ""
                threats.extend(self.scan_text(content, location=f"memory:{msg.id}"))

        except (OSError, ValueError, ImportError, TypeError):
            # If storage is not available, return empty list
            pass

        return threats

    def scan_messages(self, messages: list[dict[str, Any]]) -> list[InjectionThreat]:
        """Scan a list of messages for injection patterns.

        Args:
            messages: List of message dicts

        Returns:
            List of detected threats
        """
        threats = []

        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")

            # Scan content
            content = msg.get("content", "")
            if isinstance(content, str):
                threats.extend(self.scan_text(content, location=f"message[{i}].{role}"))
            elif isinstance(content, list):
                for j, block in enumerate(content):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if isinstance(text, str):
                            threats.extend(
                                self.scan_text(
                                    text, location=f"message[{i}].{role}[{j}]"
                                )
                            )

            # Scan tool calls if present
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        args = tc.get("arguments", "")
                        if isinstance(args, str):
                            threats.extend(
                                self.scan_text(args, location=f"tool_call[{i}]")
                            )

        return threats

    def is_safe(self, text: str) -> bool:
        """Check if text is safe (no injection patterns).

        Args:
            text: Text to check

        Returns:
            True if no threats detected
        """
        return len(self.scan_text(text)) == 0
