"""User modeling module.

This module provides classes for modeling user preferences, goals, and context.
"""

import json
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class UserPreference:
    """User preference with confidence tracking."""

    key: str
    value: str
    confidence: float
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPreference":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            confidence=data["confidence"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class UserGoal:
    """User goal with status tracking."""

    description: str
    status: str
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserGoal":
        """Create from dictionary."""
        return cls(
            description=data["description"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class UserModel:
    """User model for tracking preferences and context."""

    def __init__(self, long_term_memory):
        """Initialize user model.

        Args:
            long_term_memory: LongTermMemory instance for persistence
        """
        self.memory = long_term_memory
        self.preferences: dict[str, UserPreference] = {}
        self.goals: list[UserGoal] = []
        self.context: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load user model from memory."""
        data = self.memory.read_user()
        if data:
            try:
                model = json.loads(data)
                self.preferences = {
                    k: UserPreference.from_dict(v)
                    for k, v in model.get("preferences", {}).items()
                }
                self.goals = [
                    UserGoal.from_dict(g) for g in model.get("goals", [])
                ]
                self.context = model.get("context", {})
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def _save(self) -> None:
        """Save user model to memory."""
        model = {
            "preferences": {k: p.to_dict() for k, p in self.preferences.items()},
            "goals": [g.to_dict() for g in self.goals],
            "context": self.context,
        }
        self.memory.write_user(json.dumps(model, indent=2))

    def add_preference(self, key: str, value: str, confidence: float = 1.0) -> None:
        """Add or update preference.

        Args:
            key: Preference key
            value: Preference value
            confidence: Confidence level (0.0 to 1.0)
        """
        self.preferences[key] = UserPreference(
            key=key, value=value, confidence=confidence
        )
        self._save()

    def get_preference(self, key: str) -> Optional[str]:
        """Get preference value.

        Args:
            key: Preference key

        Returns:
            Preference value or None
        """
        pref = self.preferences.get(key)
        return pref.value if pref else None

    def get_all_preferences(self) -> dict[str, str]:
        """Get all preferences.

        Returns:
            Dictionary of key-value pairs
        """
        return {k: p.value for k, p in self.preferences.items()}

    def add_goal(self, description: str) -> None:
        """Add user goal.

        Args:
            description: Goal description
        """
        goal = UserGoal(description=description, status="active")
        self.goals.append(goal)
        self._save()

    def update_goal_status(self, index: int, status: str) -> None:
        """Update goal status.

        Args:
            index: Goal index
            status: New status ("active", "completed", "abandoned")
        """
        if 0 <= index < len(self.goals):
            self.goals[index].status = status
            self._save()

    def get_goals_by_status(self, status: str) -> list[UserGoal]:
        """Get goals filtered by status.

        Args:
            status: Status to filter by

        Returns:
            List of goals with matching status
        """
        return [g for g in self.goals if g.status == status]

    def update_context(self, key: str, value: Any) -> None:
        """Update context.

        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value
        self._save()


__all__ = ["UserPreference", "UserGoal", "UserModel"]
