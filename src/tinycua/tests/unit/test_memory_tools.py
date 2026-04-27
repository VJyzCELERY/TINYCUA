"""Tests for memory tools in tinycua package."""

import tempfile
from pathlib import Path


class TestMemoryTools:
    """Test memory tool functions."""

    def test_tools_with_invoke(self):
        """Test memory tools using invoke method."""
        from tinycua_sdk.tools.memory import LocalMemoryBackend
        from tinycua.agent.tools.memory_tools import (
            forget,
            list_memory,
            recall,
            remember,
            set_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))
            set_memory_backend(storage)

            remember.invoke(key="name", value="Bob")
            result = recall.invoke(key="name")
            assert result["found"] is True
            assert result["value"] == "Bob"

            result = list_memory.invoke()
            assert "name" in result["keys"]

            forget.invoke(key="name")
            result = recall.invoke(key="name")
            assert result["found"] is False
