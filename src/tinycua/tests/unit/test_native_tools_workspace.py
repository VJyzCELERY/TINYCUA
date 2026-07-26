"""Workspace confinement contracts for native tools."""

from __future__ import annotations

from pathlib import Path


def test_file_tools_resolve_relative_paths_inside_bound_workspace(
    tmp_path: Path,
) -> None:
    """Bound file tools use the session workspace, not process cwd."""
    from tinycua.agent.tools.native.files import list_files, read_file, write_file

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    for native_tool in (read_file, write_file, list_files):
        native_tool.bind_workspace(workspace)
    try:
        result = write_file("nested/example.txt", "workspace content")
        assert result["success"] is True
        assert (workspace / "nested" / "example.txt").read_text() == "workspace content"

        assert read_file("nested/example.txt") == "workspace content"
        listed = list_files("nested")
        # FR-035: list_files returns workspace-relative paths (relative to
        # the workspace root, not the listed directory).
        assert listed == ["nested/example.txt"]

        denied = read_file(str(outside))
        assert isinstance(denied, dict)
        assert "outside workspace" in denied["error"]
    finally:
        for native_tool in (read_file, write_file, list_files):
            native_tool.bind_workspace(None)


def test_shell_and_python_tools_execute_from_bound_workspace(tmp_path: Path) -> None:
    """Execution tools run with cwd fixed to the bound session workspace."""
    from tinycua.agent.tools.native.python_exec import run_python
    from tinycua.agent.tools.native.shell import run_shell

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for native_tool in (run_shell, run_python):
        native_tool.bind_workspace(workspace)
    try:
        pwd_result = run_shell("pwd")
        assert pwd_result["exit_code"] == 0
        assert pwd_result["stdout"].strip() == str(workspace)

        py_result = run_python(
            "from pathlib import Path; Path('marker.txt').write_text('ok')"
        )
        assert py_result["exit_code"] == 0
        assert (workspace / "marker.txt").read_text() == "ok"
    finally:
        for native_tool in (run_shell, run_python):
            native_tool.bind_workspace(None)
