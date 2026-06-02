"""Unit tests for tool constants."""

from __future__ import annotations

from tinycua_sdk.tools.decorators import Tool


def test_native_base_tools_importable():
    """NATIVE_BASE_TOOLS is importable and is a list of seven native tools."""
    from tinycua.constants.tools import NATIVE_BASE_TOOLS

    assert isinstance(NATIVE_BASE_TOOLS, list)
    assert len(NATIVE_BASE_TOOLS) == 7


def test_native_base_tools_are_tool_instances():
    """All items in NATIVE_BASE_TOOLS are Tool instances."""
    from tinycua.constants.tools import NATIVE_BASE_TOOLS

    for t in NATIVE_BASE_TOOLS:
        assert isinstance(t, Tool), f"{t} should be a Tool instance"
        assert hasattr(t, "name")
        assert hasattr(t, "parameters")


def test_native_base_tools_names():
    """NATIVE_BASE_TOOLS contains the expected tool names."""
    from tinycua.constants.tools import NATIVE_BASE_TOOLS

    tool_names = sorted(t.name for t in NATIVE_BASE_TOOLS)
    expected = sorted(
        ["run_shell", "read_file", "write_file", "edit_file", "list_files", "fetch_url", "run_python"]
    )
    assert tool_names == expected


def test_read_only_task_tools_forward_ref():
    """READ_ONLY_TASK_TOOLS exists as a forward reference (empty list for M1)."""
    from tinycua.constants.tools import READ_ONLY_TASK_TOOLS

    # It should be a list (empty for now, placeholder for M2)
    assert isinstance(READ_ONLY_TASK_TOOLS, list)
