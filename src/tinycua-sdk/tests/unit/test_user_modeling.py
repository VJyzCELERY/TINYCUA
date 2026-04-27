"""Tests for user modeling system.

This module tests the user modeling feature which captures and utilizes
user preferences, communication patterns, and context to personalize
agent interactions.
"""

import json
import pytest
from unittest.mock import MagicMock

from tinycua_sdk.modeling.user import UserPreference, UserGoal, UserModel


class TestUserPreference:
    """Tests for UserPreference dataclass."""

    def test_user_preference_creation(self):
        """UserPreference can be created with basic info."""
        pref = UserPreference(
            key="tone", value="casual", confidence=0.8
        )
        assert pref.key == "tone"
        assert pref.value == "casual"
        assert pref.confidence == 0.8

    def test_user_preference_to_dict(self):
        """UserPreference can be serialized to dict."""
        pref = UserPreference(key="tone", value="casual", confidence=0.8)
        data = pref.to_dict()
        assert data["key"] == "tone"
        assert data["value"] == "casual"
        assert data["confidence"] == 0.8
        assert "updated_at" in data

    def test_user_preference_from_dict(self):
        """UserPreference can be deserialized from dict."""
        data = {
            "key": "tone",
            "value": "formal",
            "confidence": 0.9,
            "updated_at": "2024-01-01T00:00:00",
        }
        pref = UserPreference.from_dict(data)
        assert pref.key == "tone"
        assert pref.value == "formal"
        assert pref.confidence == 0.9


class TestUserGoal:
    """Tests for UserGoal dataclass."""

    def test_user_goal_creation(self):
        """UserGoal can be created with description."""
        goal = UserGoal(description="Learn Python", status="active")
        assert goal.description == "Learn Python"
        assert goal.status == "active"

    def test_user_goal_to_dict(self):
        """UserGoal can be serialized to dict."""
        goal = UserGoal(description="Learn Python", status="active")
        data = goal.to_dict()
        assert data["description"] == "Learn Python"
        assert data["status"] == "active"
        assert "created_at" in data

    def test_user_goal_from_dict(self):
        """UserGoal can be deserialized from dict."""
        data = {
            "description": "Learn Python",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00",
        }
        goal = UserGoal.from_dict(data)
        assert goal.description == "Learn Python"
        assert goal.status == "completed"


class TestUserModel:
    """Tests for UserModel class."""

    @pytest.fixture
    def mock_memory(self):
        """Create mock memory."""
        memory = MagicMock()
        memory.read_user.return_value = ""
        memory.write_user.return_value = {"success": True}
        return memory

    def test_user_model_creation(self, mock_memory):
        """UserModel can be created."""
        model = UserModel(mock_memory)
        assert model.memory == mock_memory

    def test_add_preference(self, mock_memory):
        """UserModel can add preference."""
        model = UserModel(mock_memory)
        model.add_preference("tone", "casual", 0.8)
        assert model.get_preference("tone") == "casual"

    def test_get_preference_missing(self, mock_memory):
        """UserModel returns None for missing preference."""
        model = UserModel(mock_memory)
        assert model.get_preference("missing") is None

    def test_get_all_preferences(self, mock_memory):
        """UserModel can get all preferences."""
        model = UserModel(mock_memory)
        model.add_preference("tone", "casual")
        model.add_preference("format", "json")
        prefs = model.get_all_preferences()
        assert prefs["tone"] == "casual"
        assert prefs["format"] == "json"

    def test_add_goal(self, mock_memory):
        """UserModel can add goal."""
        model = UserModel(mock_memory)
        model.add_goal("Learn Python")
        assert len(model.goals) == 1
        assert model.goals[0].description == "Learn Python"

    def test_update_context(self, mock_memory):
        """UserModel can update context."""
        model = UserModel(mock_memory)
        model.update_context("current_task", "testing")
        assert model.context["current_task"] == "testing"

    def test_persistence(self, mock_memory):
        """UserModel persists data to memory."""
        model = UserModel(mock_memory)
        model.add_preference("tone", "casual")
        model.add_goal("Learn Python")
        model.update_context("task", "test")
        assert mock_memory.write_user.called


class TestUserModelPersistence:
    """Tests for UserModel persistence."""

    @pytest.fixture
    def mock_memory_with_data(self):
        """Create mock memory with existing data."""
        memory = MagicMock()
        data = {
            "preferences": {
                "tone": {
                    "key": "tone",
                    "value": "formal",
                    "confidence": 0.9,
                    "updated_at": "2024-01-01T00:00:00",
                }
            },
            "goals": [
                {
                    "description": "Test goal",
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00",
                }
            ],
            "context": {"key": "value"},
        }
        memory.read_user.return_value = json.dumps(data)
        memory.write_user.return_value = {"success": True}
        return memory

    def test_load_existing_preferences(self, mock_memory_with_data):
        """UserModel loads existing preferences."""
        model = UserModel(mock_memory_with_data)
        assert model.get_preference("tone") == "formal"

    def test_load_existing_goals(self, mock_memory_with_data):
        """UserModel loads existing goals."""
        model = UserModel(mock_memory_with_data)
        assert len(model.goals) == 1
        assert model.goals[0].description == "Test goal"

    def test_load_existing_context(self, mock_memory_with_data):
        """UserModel loads existing context."""
        model = UserModel(mock_memory_with_data)
        assert model.context["key"] == "value"
