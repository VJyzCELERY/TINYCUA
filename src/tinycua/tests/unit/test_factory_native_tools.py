"""Factory contracts for optional native tool wiring."""

from __future__ import annotations

from pathlib import Path

from tinycua.config.session_config import NativeToolPolicy, SessionConfig
from tinycua.factory import create_tinycua_agent


def test_factory_can_enable_workspace_bound_native_tools(tmp_path: Path) -> None:
    """Native tools are opt-in and attached through the public factory API."""
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=True,
    )

    tool_names = {tool.name for tool in agent.tools}
    assert {"read_file", "write_file", "list_files", "run_shell", "run_python"} <= tool_names
    assert agent.loop.get_state_snapshot()["workspace_dir"] == str(tmp_path)


def test_factory_native_tool_policy_filters_enabled_tools(tmp_path: Path) -> None:
    """NativeToolPolicy can restrict which native tools are exposed."""
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=True,
        native_tool_policy=NativeToolPolicy(allowed_tool_names=frozenset({"read_file"})),
    )

    assert {tool.name for tool in agent.tools} == {"read_file"}
