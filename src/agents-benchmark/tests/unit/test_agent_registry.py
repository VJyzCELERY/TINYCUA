"""Unit tests for AgentRegistry."""

from __future__ import annotations

import pytest

from agents_benchmark.agent_registry import AgentRegistry


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_and_get(self):
        """register must store adapter, get must retrieve it."""
        registry = AgentRegistry()
        registry.register("hermes", str)  # using str as a dummy class
        assert registry.get("hermes") is str

    def test_get_unknown_adapter_raises_keyerror(self):
        """get must raise KeyError for unknown adapter names."""
        registry = AgentRegistry()
        with pytest.raises(KeyError, match="No adapter registered"):
            registry.get("unknown")

    def test_list_all_returns_registered_names(self):
        """list_all must return all registered adapter names."""
        registry = AgentRegistry()
        registry.register("hermes", str)
        registry.register("codex", int)
        names = registry.list_all()
        assert "hermes" in names
        assert "codex" in names

    def test_register_overwrites_existing(self):
        """register must overwrite an existing adapter with the same name."""
        registry = AgentRegistry()
        registry.register("hermes", str)
        registry.register("hermes", int)
        assert registry.get("hermes") is int
