"""Unit tests for workspace path normalization + relative path reporting (FR-035)."""

from __future__ import annotations

from pathlib import Path

from tinycua.agent.tools.native.context import bind_workspace, resolve_workspace_path


def _doubled_path(workspace: Path, suffix: str = "report.md") -> str:
    """Construct a doubled workspace path (full workspace path repeated)."""
    ws_after_root = Path(*workspace.parts[1:])
    return str(workspace / ws_after_root / suffix)


class TestDoubledWorkspacePathStripped:
    """Part A: resolve_workspace_path strips repeated workspace prefixes."""

    def test_doubled_path_stripped_to_canonical(self, tmp_path: Path):
        workspace = tmp_path / "workspace" / "experiment-2"
        workspace.mkdir(parents=True)
        (workspace / "report.md").write_text("content")
        bind_workspace(workspace)
        try:
            resolved = resolve_workspace_path(_doubled_path(workspace))
            assert resolved == workspace / "report.md"
        finally:
            bind_workspace(None)

    def test_single_prefix_path_preserved(self, tmp_path: Path):
        workspace = tmp_path / "workspace" / "experiment-2"
        workspace.mkdir(parents=True)
        (workspace / "report.md").write_text("content")
        bind_workspace(workspace)
        try:
            single = str(workspace / "report.md")
            resolved = resolve_workspace_path(single)
            assert resolved == workspace / "report.md"
        finally:
            bind_workspace(None)

    def test_relative_path_unchanged(self, tmp_path: Path):
        workspace = tmp_path / "workspace" / "experiment-2"
        workspace.mkdir(parents=True)
        (workspace / "report.md").write_text("content")
        bind_workspace(workspace)
        try:
            resolved = resolve_workspace_path("report.md")
            assert resolved == workspace / "report.md"
        finally:
            bind_workspace(None)

    def test_doubled_path_preferred_over_doubled_file(self, tmp_path: Path):
        """Even if the doubled file exists, the canonical path is returned."""
        workspace = tmp_path / "workspace" / "experiment-2"
        workspace.mkdir(parents=True)
        (workspace / "report.md").write_text("canonical")
        # Also create the doubled path as a file.
        ws_after_root = Path(*workspace.parts[1:])
        doubled_dir = workspace / ws_after_root
        doubled_dir.mkdir(parents=True, exist_ok=True)
        (doubled_dir / "report.md").write_text("doubled")
        bind_workspace(workspace)
        try:
            resolved = resolve_workspace_path(_doubled_path(workspace))
            assert resolved == workspace / "report.md"
        finally:
            bind_workspace(None)

    def test_re_root_non_workspace_absolute_preserved(self, tmp_path: Path):
        """Paths not under the workspace still get re-rooted (existing logic)."""
        workspace = tmp_path / "workspace" / "experiment-2"
        workspace.mkdir(parents=True)
        # Create a file that looks like an absolute subpath under the workspace.
        (workspace / "backend" / "api.py").parent.mkdir(parents=True, exist_ok=True)
        (workspace / "backend" / "api.py").write_text("code")
        bind_workspace(workspace)
        try:
            # /backend/api.py → re-rooted to workspace/backend/api.py
            resolved = resolve_workspace_path("/backend/api.py")
            assert resolved == workspace / "backend" / "api.py"
        finally:
            bind_workspace(None)

    def test_nested_doubled_path_with_subdir(self, tmp_path: Path):
        """Doubled path with a subdirectory is also stripped correctly."""
        workspace = tmp_path / "workspace" / "experiment-2"
        (workspace / "src").mkdir(parents=True)
        (workspace / "src" / "main.py").write_text("code")
        bind_workspace(workspace)
        try:
            resolved = resolve_workspace_path(_doubled_path(workspace, "src/main.py"))
            assert resolved == workspace / "src" / "main.py"
        finally:
            bind_workspace(None)


class TestToolResultsReturnRelPath:
    """Part B: file tool results include a workspace-relative rel_path."""

    def test_write_file_returns_rel_path(self, tmp_path: Path):
        bind_workspace(tmp_path)
        try:
            from tinycua.agent.tools.native.files import write_file

            result = write_file("report.md", "hello")
            assert result["success"] is True
            assert "rel_path" in result
            assert result["rel_path"] == "report.md"
        finally:
            bind_workspace(None)

    def test_append_file_returns_rel_path(self, tmp_path: Path):
        bind_workspace(tmp_path)
        try:
            from tinycua.agent.tools.native.files import append_file

            (tmp_path / "report.md").write_text("base\n")
            result = append_file("report.md", "appended\n")
            assert result["success"] is True
            assert "rel_path" in result
            assert result["rel_path"] == "report.md"
        finally:
            bind_workspace(None)

    def test_str_replace_returns_rel_path(self, tmp_path: Path):
        bind_workspace(tmp_path)
        try:
            from tinycua.agent.tools.native.files import str_replace

            (tmp_path / "code.py").write_text("old text")
            result = str_replace("code.py", old_string="old", new_string="new")
            assert result["success"] is True
            assert "rel_path" in result
            assert result["rel_path"] == "code.py"
        finally:
            bind_workspace(None)

    def test_str_replace_error_returns_rel_path(self, tmp_path: Path):
        bind_workspace(tmp_path)
        try:
            from tinycua.agent.tools.native.files import str_replace

            (tmp_path / "code.py").write_text("some text")
            result = str_replace("code.py", old_string="nonexistent", new_string="x")
            assert result["success"] is False
            assert "rel_path" in result
            assert result["rel_path"] == "code.py"
        finally:
            bind_workspace(None)

    def test_list_files_returns_relative_paths(self, tmp_path: Path):
        bind_workspace(tmp_path)
        try:
            from tinycua.agent.tools.native.files import list_files

            (tmp_path / "report.md").write_text("r")
            (tmp_path / "src").mkdir()
            (tmp_path / "src" / "main.py").write_text("m")
            result = list_files(".")
            assert isinstance(result, list)
            # Paths should be relative, not absolute.
            assert all(not str(p).startswith("/") for p in result)
            assert "report.md" in result
        finally:
            bind_workspace(None)

    def test_search_files_content_matches_use_relative_paths(self, tmp_path: Path):
        bind_workspace(tmp_path)
        try:
            from tinycua.agent.tools.native.files import search_files

            (tmp_path / "report.md").write_text("hello world\nfoo bar\nhello again\n")
            result = search_files("hello", target="content", path=".", output_mode="content")
            assert isinstance(result, list)
            # The match line should use a relative path, not absolute.
            assert any("report.md" in str(line) and not str(line).startswith("/") for line in result)
        finally:
            bind_workspace(None)
