"""Personality module.

This module provides classes for defining and applying agent personality traits.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PersonalityTraits:
    """Personality traits for agent behavior."""

    name: str = "helpful assistant"
    tone: str = "friendly"
    verbosity: str = "balanced"
    humor: float = 0.3
    empathy: float = 0.7
    creativity: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "tone": self.tone,
            "verbosity": self.verbosity,
            "humor": self.humor,
            "empathy": self.empathy,
            "creativity": self.creativity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonalityTraits":
        """Create from dictionary."""
        return cls(**data)


class Personality:
    """Personality system for agent behavior customization."""

    DEFAULT_TRAITS = PersonalityTraits()

    def __init__(self, long_term_memory):
        """Initialize personality system.

        Args:
            long_term_memory: LongTermMemory instance for persistence
        """
        self.memory = long_term_memory
        self.traits = PersonalityTraits()
        self._load()

    def _backup_user(self) -> None:
        """Create backup of USER.md before writes."""
        user_file = self.memory._file_path("USER.md")
        if user_file.exists():
            backup_file = user_file.with_suffix(".md.bak")
            shutil.copy2(user_file, backup_file)
            self._cleanup_backups(user_file)

    def _cleanup_backups(self, user_file: Path) -> None:
        """Clean up old backup files.

        Args:
            user_file: Path to the user file
        """
        backup_files = sorted(
            user_file.parent.glob(f"{user_file.stem}*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for backup in backup_files[5:]:
            backup.unlink(missing_ok=True)

    def _load(self) -> None:
        """Load personality from memory."""
        data = self.memory.read_user()
        if data:
            try:
                model = json.loads(data)
                if "personality" in model:
                    self.traits = PersonalityTraits.from_dict(model["personality"])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def _save(self) -> None:
        """Save personality to memory."""
        self._backup_user()
        data = self.memory.read_user()
        model = json.loads(data) if data else {}

        model["personality"] = self.traits.to_dict()
        self.memory.write_user(json.dumps(model, indent=2))

    def _merge_strategy(
        self, current: dict[str, Any], updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge strategy for personality updates.

        Args:
            current: Current personality data
            updates: Updated personality data

        Returns:
            Merged personality data
        """
        merged = current.copy()
        for key, value in updates.items():
            if value is not None:
                merged[key] = value
        return merged

    def set_traits(self, **kwargs) -> None:
        """Modify personality traits.

        Args:
            **kwargs: Trait key-value pairs to update
        """
        current = self.traits.to_dict()
        updates = {k: v for k, v in kwargs.items() if v is not None}
        merged = self._merge_strategy(current, updates)
        self.traits = PersonalityTraits.from_dict(merged)
        self._save()

    def get_traits(self) -> PersonalityTraits:
        """Get current traits.

        Returns:
            PersonalityTraits instance
        """
        return self.traits

    def apply_to_response(self, response: str) -> str:
        """Apply personality to response.

        Args:
            response: Original response string

        Returns:
            Modified response string
        """
        result = response

        if self.traits.tone == "formal":
            result = result.replace("hey", "hello")
            result = result.replace("gonna", "going to")
            result = result.replace("wanna", "want to")
        elif self.traits.tone == "friendly":
            if "hello" in result.lower():
                result = result.replace("hello", "hey", 1)

        if self.traits.verbosity == "concise" and len(result) > 200:
            result = result[:200] + "..."
        elif self.traits.verbosity == "detailed" and len(result) < 50:
            result = result + " Let me know if you need more details."

        if self.traits.humor > 0.7 and "error" in result.lower():
            result = result.replace("error", "oopsie")

        return result


__all__ = ["PersonalityTraits", "Personality"]
