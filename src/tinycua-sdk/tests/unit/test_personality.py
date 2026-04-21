"""Tests for personality system.

This module tests the personality system which defines agent behavior
patterns, communication styles, and response characteristics.
"""

import json
import pytest
from unittest.mock import MagicMock

from tinycua_sdk.modeling.personality import PersonalityTraits, Personality
from tinycua_sdk.modeling.profiler import CommunicationStyle, CommunicationProfiler


class TestPersonalityTraits:
    """Tests for PersonalityTraits dataclass."""

    def test_personality_traits_defaults(self):
        """PersonalityTraits has default values."""
        traits = PersonalityTraits()
        assert traits.name == "helpful assistant"
        assert traits.tone == "friendly"
        assert traits.verbosity == "balanced"
        assert traits.humor == 0.3
        assert traits.empathy == 0.7
        assert traits.creativity == 0.5

    def test_personality_traits_custom(self):
        """PersonalityTraits can be customized."""
        traits = PersonalityTraits(
            name="custom",
            tone="formal",
            verbosity="concise",
            humor=0.1,
            empathy=0.5,
            creativity=0.8,
        )
        assert traits.name == "custom"
        assert traits.tone == "formal"
        assert traits.verbosity == "concise"

    def test_personality_traits_to_dict(self):
        """PersonalityTraits can be serialized."""
        traits = PersonalityTraits(name="test")
        data = traits.to_dict()
        assert data["name"] == "test"
        assert "tone" in data

    def test_personality_traits_from_dict(self):
        """PersonalityTraits can be deserialized."""
        data = {
            "name": "custom",
            "tone": "formal",
            "verbosity": "detailed",
            "humor": 0.5,
            "empathy": 0.8,
            "creativity": 0.6,
        }
        traits = PersonalityTraits.from_dict(data)
        assert traits.name == "custom"
        assert traits.tone == "formal"


class TestPersonality:
    """Tests for Personality class."""

    @pytest.fixture
    def mock_memory(self):
        """Create mock memory."""
        memory = MagicMock()
        memory.read_user.return_value = ""
        memory.write_user.return_value = {"success": True}
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        memory._file_path.return_value = mock_path
        return memory

    def test_personality_creation(self, mock_memory):
        """Personality can be created."""
        personality = Personality(mock_memory)
        assert personality.memory == mock_memory

    def test_default_personality(self, mock_memory):
        """Personality defaults to helpful assistant."""
        personality = Personality(mock_memory)
        assert personality.traits.name == "helpful assistant"

    def test_set_traits(self, mock_memory):
        """Personality can set traits."""
        personality = Personality(mock_memory)
        personality.set_traits(tone="formal", humor=0.1)
        assert personality.traits.tone == "formal"
        assert personality.traits.humor == 0.1

    def test_get_traits(self, mock_memory):
        """Personality can get traits."""
        personality = Personality(mock_memory)
        traits = personality.get_traits()
        assert isinstance(traits, PersonalityTraits)

    def test_apply_to_response_formal(self, mock_memory):
        """Personality applies formal tone to response."""
        personality = Personality(mock_memory)
        personality.set_traits(tone="formal")
        response = personality.apply_to_response("hey there")
        assert "hello" in response

    def test_apply_to_response_concise(self, mock_memory):
        """Personality applies concise verbosity."""
        personality = Personality(mock_memory)
        personality.set_traits(verbosity="concise")
        long_response = "a" * 300
        response = personality.apply_to_response(long_response)
        assert len(response) <= 203

    def test_persistence(self, mock_memory):
        """Personality persists to memory."""
        personality = Personality(mock_memory)
        personality.set_traits(tone="formal")
        assert mock_memory.write_user.called


class TestPersonalityMerge:
    """Tests for personality merge strategy."""

    @pytest.fixture
    def mock_memory(self):
        """Create mock memory."""
        memory = MagicMock()
        memory.read_user.return_value = ""
        memory.write_user.return_value = {"success": True}
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        memory._file_path.return_value = mock_path
        return memory

    def test_merge_strategy(self, mock_memory):
        """Personality merge strategy works."""
        personality = Personality(mock_memory)
        current = {"name": "old", "tone": "friendly"}
        updates = {"tone": "formal"}
        merged = personality._merge_strategy(current, updates)
        assert merged["name"] == "old"
        assert merged["tone"] == "formal"


class TestCommunicationProfiler:
    """Tests for CommunicationProfiler class."""

    def test_profiler_creation(self):
        """CommunicationProfiler can be created."""
        profiler = CommunicationProfiler()
        assert profiler.style.formality == 0.5

    def test_profiler_sensitivity(self):
        """CommunicationProfiler has configurable sensitivity."""
        profiler = CommunicationProfiler(sensitivity=5)
        assert profiler._sensitivity == 5

    def test_analyze_formality(self):
        """CommunicationProfiler detects formal language."""
        profiler = CommunicationProfiler(sensitivity=3)
        messages = [
            {"content": "Please help me"},
            {"content": "Thank you"},
            {"content": "Would you mind"},
        ]
        for msg in messages:
            profiler.analyze(msg)
        assert profiler.style.formality > 0.5

    def test_analyze_casual(self):
        """CommunicationProfiler detects casual language."""
        profiler = CommunicationProfiler(sensitivity=3)
        messages = [
            {"content": "hey there"},
            {"content": "yeah sure"},
            {"content": "gonna do it"},
        ]
        for msg in messages:
            profiler.analyze(msg)
        assert profiler.style.formality < 0.5

    def test_analyze_verbosity(self):
        """CommunicationProfiler detects verbosity."""
        profiler = CommunicationProfiler(sensitivity=2)
        messages = [
            {"content": "a" * 500},
            {"content": "b" * 600},
        ]
        for msg in messages:
            profiler.analyze(msg)
        assert profiler.style.verbosity > 0.5

    def test_get_style(self):
        """CommunicationProfiler returns current style."""
        profiler = CommunicationProfiler()
        style = profiler.get_style()
        assert isinstance(style, CommunicationStyle)

    def test_set_sensitivity(self):
        """CommunicationProfiler can update sensitivity."""
        profiler = CommunicationProfiler()
        profiler.set_sensitivity(20)
        assert profiler._sensitivity == 20
