"""Integration tests for loop configuration."""

import tempfile
from pathlib import Path

import pytest

from tinycua_sdk.agent.loader import AgentLoader
from tinycua_sdk.agent.loop import DefaultLoop, ReactLoop, resolve_loop

class TestLoopConfigLoading:
    """Test loading agents with loop configurations."""

    def test_load_agent_with_default_loop_string(self):
        """Test loading agent with loop: 'default'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_md = Path(tmpdir) / "AGENT.md"
            agent_md.write_text("""---
name: test-agent
model: gpt-4o-mini
loop: "default"
---

You are a helpful assistant.
""")
            loader = AgentLoader()
            config = loader.load_from_markdown(agent_md)
            assert config.loop == "default"

    def test_load_agent_with_react_loop_string(self):
        """Test loading agent with loop: 'react'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_md = Path(tmpdir) / "AGENT.md"
            agent_md.write_text("""---
name: test-agent
model: gpt-4o-mini
loop: "react"
---

You are a helpful assistant.
""")
            loader = AgentLoader()
            config = loader.load_from_markdown(agent_md)
            assert config.loop == "react"

    def test_load_agent_with_react_dict_config(self):
        """Test loading agent with loop: {type: 'react', max_iterations: 3}."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_md = Path(tmpdir) / "AGENT.md"
            agent_md.write_text("""---
name: test-agent
model: gpt-4o-mini
loop:
  type: "react"
  max_iterations: 3
---

You are a helpful assistant.
""")
            loader = AgentLoader()
            config = loader.load_from_markdown(agent_md)
            assert config.loop == {"type": "react", "max_iterations": 3}

    def test_load_agent_without_loop(self):
        """Test loading agent without loop (defaults to None)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_md = Path(tmpdir) / "AGENT.md"
            agent_md.write_text("""---
name: test-agent
model: gpt-4o-mini
---

You are a helpful assistant.
""")
            loader = AgentLoader()
            config = loader.load_from_markdown(agent_md)
            assert config.loop is None


class TestLoopConfigResolution:
    """Test resolving loop configurations."""

    def test_resolve_string_default(self):
        """Test resolving 'default' string."""
        loop = resolve_loop("default")
        assert isinstance(loop, DefaultLoop)

    def test_resolve_string_react(self):
        """Test resolving 'react' string."""
        loop = resolve_loop("react")
        assert isinstance(loop, ReactLoop)

    def test_resolve_dict_react(self):
        """Test resolving {type: 'react', max_iterations: 3}."""
        loop = resolve_loop({"type": "react", "max_iterations": 3})
        assert isinstance(loop, ReactLoop)
        assert loop.max_iterations == 3

    def test_resolve_none(self):
        """Test resolving None."""
        loop = resolve_loop(None)
        assert isinstance(loop, DefaultLoop)

    def test_resolve_instance(self):
        """Test resolving a DefaultLoop instance."""
        original = DefaultLoop()
        loop = resolve_loop(original)
        assert loop is original


class TestBackwardCompatibility:
    """Test backward compatibility with programmatic loop creation."""

    def test_programmatic_loop_instance(self):
        """Test that programmatic loop instances still work."""
        loop = DefaultLoop()
        resolved = resolve_loop(loop)
        assert resolved is loop

    def test_programmatic_react_loop(self):
        """Test that programmatic ReactLoop instances still work."""
        loop = ReactLoop(max_iterations=10)
        resolved = resolve_loop(loop)
        assert resolved is loop
        assert resolved.max_iterations == 10
