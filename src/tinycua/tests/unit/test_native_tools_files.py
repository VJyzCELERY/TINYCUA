"""Unit tests for files.py — testing path resolution, edge cases."""

import os
import tempfile
from pathlib import Path

import pytest


# --- read_file edge cases ---


def test_read_file_path_resolution_absolute():
    """Absolute paths are used as-is."""
    from tinycua.agent.tools.native.files import read_file

    result = read_file("/nonexistent/absolute/path.txt")
    assert isinstance(result, dict)
    assert "error" in result


def test_read_file_path_resolution_relative():
    """Relative paths are resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path("subdir").mkdir()
            Path("subdir/test.txt").write_text("relative content\n")

            from tinycua.agent.tools.native.files import read_file

            result = read_file("subdir/test.txt")
            assert result == "relative content\n"
    finally:
        os.chdir(original_cwd)


def test_read_file_dot_slash_prefix():
    """Paths with ./ prefix are treated as relative."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path("dotfile.txt").write_text("dot content\n")

            from tinycua.agent.tools.native.files import read_file

            result = read_file("./dotfile.txt")
            assert result == "dot content\n"
    finally:
        os.chdir(original_cwd)


def test_read_file_permission_denied():
    """Permission denied returns error dict (skip on Windows)."""
    import platform

    if platform.system() == "Windows":
        pytest.skip("Permission tests not supported on Windows")

    from tinycua.agent.tools.native.files import read_file

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"secret\n")
        path = f.name
    try:
        os.chmod(path, 0o000)  # Remove all permissions
        result = read_file(path)
        assert isinstance(result, dict)
        assert "error" in result
        assert (
            "permission" in result["error"].lower()
            or "denied" in result["error"].lower()
        )
    finally:
        os.chmod(path, 0o644)  # Restore for cleanup
        os.unlink(path)


def test_read_file_not_a_file():
    """Reading a directory returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(tmpdir)
        assert isinstance(result, dict)
        assert "error" in result


def test_read_file_start_zero_returns_error():
    """start=0 (invalid, must be >= 1) returns error."""
    from tinycua.agent.tools.native.files import read_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello\nworld\n")
        path = f.name
    try:
        result = read_file(path, start=0)
        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid start line" in result["error"]
    finally:
        os.unlink(path)


def test_read_file_truncation_message_format():
    """Truncation message matches expected format with resume hint."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("x" * 150 * 1024)
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert "[Truncated:" in result
        assert "lines remaining" in result
        assert "bytes not shown" in result
        assert "Set start=" in result
    finally:
        os.unlink(path)


# --- write_file edge cases ---


def test_write_file_empty_content():
    """Writing empty content creates empty file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "empty.txt")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "")
        assert result["success"] is True
        assert result["chars_written"] == 0
        assert Path(filepath).read_text() == ""


def test_write_file_binary_content():
    """Writing text with binary-looking content works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "binary.txt")
        from tinycua.agent.tools.native.files import write_file

        content = "hello\x00world\x01test"
        result = write_file(filepath, content)
        assert result["success"] is True
        assert Path(filepath).read_bytes() == content.encode("utf-8")


# --- edit_file edge cases ---


def test_edit_file_with_newline_content():
    """Editing with content that ends with newline is handled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "edit_nl.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=2, content="A\nB\n", offset=2)
        assert result["success"] is True
        assert result["lines_replaced"] == 2
        content = Path(filepath).read_text()
        # The replacement content's trailing newline should be respected
        assert "A\nB\n" in content


def test_edit_file_start_zero_returns_error():
    """edit_file with start=0 (invalid, must be >= 1) returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "edit_start_zero.txt")
        Path(filepath).write_text("line 1\nline 2\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=0, content="new")
        assert result["success"] is False
        assert "Invalid start line" in result["error"]


def test_edit_file_single_line_no_trailing_newline():
    """edit_file on a file without trailing newline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "no_nl.txt")
        Path(filepath).write_text("line 1\nline 2")  # no trailing newline
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=2, content="REPLACED")
        assert result["success"] is True
        result_text = Path(filepath).read_text()
        assert result_text == "line 1\nREPLACED"


# --- list_files edge cases ---


def test_list_files_no_match():
    """Pattern with no matches returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "readme.md").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir, "*.py")
        assert result == []


def test_list_files_with_subdirectories():
    """list_files only returns files at the top level (non-recursive)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "file.txt").touch()
        Path(tmpdir, "subdir").mkdir()
        Path(tmpdir, "subdir", "nested.txt").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        # Only top-level files, not recursive
        assert len(result) == 1
        assert any(p.endswith("file.txt") for p in result)


def test_list_files_on_file_returns_error():
    """list_files on a file path (not a directory) returns error."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"content")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import list_files

        result = list_files(path)
        assert isinstance(result, dict)
        assert "error" in result
        assert "Not a directory" in result["error"]
    finally:
        os.unlink(path)


def test_list_files_absolute_paths():
    """Returned paths are absolute."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "test.txt").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        assert len(result) == 1
        assert result[0].startswith("/")
