"""Communication profiler module.

This module provides classes for profiling user communication styles.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CommunicationStyle:
    """Communication style profile."""

    formality: float = 0.5
    verbosity: float = 0.5
    technical_level: float = 0.5

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "formality": self.formality,
            "verbosity": self.verbosity,
            "technical_level": self.technical_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "CommunicationStyle":
        """Create from dictionary."""
        return cls(**data)


class CommunicationProfiler:
    """Profile user communication style."""

    FORMAL_WORDS = ["please", "thank", "would", "could", "appreciate", "kindly"]
    CASUAL_WORDS = ["hey", "yeah", "gonna", "wanna", "cool", "awesome"]
    TECHNICAL_WORDS = [
        "api",
        "algorithm",
        "function",
        "class",
        "method",
        "parameter",
        "return",
        "import",
    ]

    def __init__(self, sensitivity: int = 10):
        """Initialize communication profiler.

        Args:
            sensitivity: Number of messages before recalculating style
        """
        self.style = CommunicationStyle(
            formality=0.5,
            verbosity=0.5,
            technical_level=0.5,
        )
        self._message_samples: list[dict[str, Any]] = []
        self._sensitivity = sensitivity

    def analyze(self, message: dict[str, Any]) -> None:
        """Analyze message for style.

        Args:
            message: Message dictionary with content key
        """
        self._message_samples.append(message)

        if len(self._message_samples) >= self._sensitivity:
            self._recalculate_style()

    def _recalculate_style(self) -> None:
        """Recalculate style based on samples."""
        content = " ".join(m.get("content", "") for m in self._message_samples)
        content_lower = content.lower()

        formal_count = sum(1 for w in self.FORMAL_WORDS if w in content_lower)
        casual_count = sum(1 for w in self.CASUAL_WORDS if w in content_lower)

        if formal_count + casual_count > 0:
            self.style.formality = formal_count / (formal_count + casual_count)

        avg_length = sum(len(m.get("content", "")) for m in self._message_samples) / len(
            self._message_samples
        )
        self.style.verbosity = min(1.0, avg_length / 500)

        tech_count = sum(1 for w in self.TECHNICAL_WORDS if w in content_lower)
        total_words = len(content.split())
        if total_words > 0:
            self.style.technical_level = min(1.0, tech_count / max(1, total_words * 0.2))

    def get_style(self) -> CommunicationStyle:
        """Get current style.

        Returns:
            CommunicationStyle instance
        """
        return self.style

    def set_sensitivity(self, sensitivity: int) -> None:
        """Set profiling sensitivity.

        Args:
            sensitivity: Number of messages before recalculating
        """
        self._sensitivity = max(1, sensitivity)


__all__ = ["CommunicationStyle", "CommunicationProfiler"]
