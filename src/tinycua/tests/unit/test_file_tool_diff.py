"""Unit tests for file-tool diff/preview (Milestone 8, FR-058)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tinycua.agent.tools.native.context import bind_workspace


class TestAppendFileDiffPreview:
    """FR-058: append_file returns diff_preview + new_file_size."""

    def test_append_returns_diff_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "report.md")
            Path(filepath).write_text("existing content\n")
            from tinycua.agent.tools.native.files import append_file

            result = append_file(filepath, content="new section\n")
            assert result["success"] is True
            assert "diff_preview" in result
            assert "new section" in result["diff_preview"]
            assert "new_file_size" in result
            assert result["new_file_size"] == len(
                "existing content\nnew section\n".encode("utf-8")
            )

    def test_append_diff_preview_has_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "report.md")
            Path(filepath).write_text("base\n")
            from tinycua.agent.tools.native.files import append_file

            result = append_file(filepath, content="appended\n")
            assert result["success"] is True
            # The diff_preview should have a marker indicating appended content.
            assert "appended" in result["diff_preview"]

    def test_append_to_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "new.md")
            from tinycua.agent.tools.native.files import append_file

            result = append_file(filepath, content="first content\n")
            assert result["success"] is True
            assert "diff_preview" in result
            assert "new_file_size" in result
            assert result["new_file_size"] == len("first content\n".encode("utf-8"))


class TestWriteFileDiffPreview:
    """FR-058: write_file returns diff_preview + new_file_size."""

    def test_write_returns_diff_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "file.txt")
            from tinycua.agent.tools.native.files import write_file

            result = write_file(filepath, content="hello world\n")
            assert result["success"] is True
            assert "diff_preview" in result
            assert "hello world" in result["diff_preview"]
            assert "new_file_size" in result
            assert result["new_file_size"] == len("hello world\n".encode("utf-8"))


class TestStrReplaceDiffPreview:
    """FR-058: str_replace returns a real unified-diff snippet (not just new_string[:200])."""

    def test_str_replace_diff_preview_is_unified_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "code.py")
            Path(filepath).write_text("def foo():\n    return 1\n")
            from tinycua.agent.tools.native.files import str_replace

            result = str_replace(
                filepath,
                old_string="return 1",
                new_string="return 42",
            )
            assert result["success"] is True
            assert "diff_preview" in result
            preview = result["diff_preview"]
            # A unified diff contains --- and +++ markers or -/+ line prefixes.
            # FR-058: should be a real difflib.unified_diff, not just new_string[:200].
            assert "-" in preview or "+" in preview
