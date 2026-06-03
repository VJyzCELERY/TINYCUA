"""Integration tests for read_file, write_file, edit_file, list_files tools."""

import os
from pathlib import Path

import pytest


# --- read_file ---


def test_read_file_full(tmp_path):
    """Read entire file when start and offset are not set."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("line 1\nline 2\nline 3\n")
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath))
    assert result == "line 1\nline 2\nline 3\n"


def test_read_file_start_only(tmp_path):
    """Read from start line to end of file."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("line 1\nline 2\nline 3\nline 4\n")
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath), start=2)
    assert result == "line 2\nline 3\nline 4\n"


def test_read_file_start_and_offset(tmp_path):
    """Read exactly offset lines from start."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("line 1\nline 2\nline 3\nline 4\n")
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath), start=2, offset=2)
    assert result == "line 2\nline 3\n"


def test_read_file_start_plus_offset_exceeds_file(tmp_path):
    """Error when start+offset exceeds file line count."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("line 1\nline 2\nline 3\n")
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath), start=2, offset=5)
    assert isinstance(result, dict)
    assert "error" in result
    assert "exceeds" in result["error"].lower()


def test_read_file_truncation(tmp_path):
    """Full-file read truncates when file exceeds internal limit."""
    filepath = tmp_path / "large.txt"
    filepath.write_text("x" * 150 * 1024)
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath))
    assert "[Truncated:" in result


def test_read_file_range_no_truncation(tmp_path):
    """Range reads bypass truncation limit entirely."""
    filepath = tmp_path / "large.txt"
    filepath.write_text("x" * 150 * 1024)
    from tinycua.tools.native.files import read_file

    # Read first 5 lines — should NOT be truncated even though file > 100KB
    result = read_file(str(filepath), start=1, offset=5)
    assert "[Truncated:" not in result


def test_read_file_not_found(tmp_path):
    """Error dict returned for missing file."""
    from tinycua.tools.native.files import read_file

    result = read_file(str(tmp_path / "nonexistent_path_file.txt"))
    assert isinstance(result, dict)
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_read_file_invalid_start_line(tmp_path):
    """Error dict returned when start exceeds file length."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("only one line\n")
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath), start=100)
    assert isinstance(result, dict)
    assert "error" in result
    assert "range" in result["error"].lower()


def test_read_file_empty(tmp_path):
    """Read an empty file returns empty string."""
    filepath = tmp_path / "empty.txt"
    filepath.write_text("")
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath))
    assert result == ""


def test_read_file_relative_path():
    """Relative path is resolved from TINYCUA_TOOL_ROOT."""
    original_cwd = os.getcwd()
    original_root = os.environ.get("TINYCUA_TOOL_ROOT")
    try:
        with pytest.MonkeyPatch.context() as mp:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                mp.setenv("TINYCUA_TOOL_ROOT", tmpdir)
                os.chdir(tmpdir)
                Path("test.txt").write_text("hello world\n")

                from tinycua.tools.native.files import read_file

                result = read_file("test.txt")
                assert result == "hello world\n"
    finally:
        os.chdir(original_cwd)
        if original_root is not None:
            os.environ["TINYCUA_TOOL_ROOT"] = original_root
        else:
            os.environ.pop("TINYCUA_TOOL_ROOT", None)


# --- write_file ---


def test_write_file_create(tmp_path):
    """Create a new file with content."""
    filepath = tmp_path / "output.txt"
    from tinycua.tools.native.files import write_file

    result = write_file(str(filepath), "hello world")
    assert result["success"] is True
    assert result["path"] == str(filepath)
    assert result["chars_written"] == len("hello world")
    assert filepath.read_text() == "hello world"


def test_write_file_overwrite(tmp_path):
    """Overwrite an existing file."""
    filepath = tmp_path / "existing.txt"
    filepath.write_text("old content")
    from tinycua.tools.native.files import write_file

    result = write_file(str(filepath), "new content")
    assert result["success"] is True
    assert filepath.read_text() == "new content"


def test_write_file_creates_parent_dirs(tmp_path):
    """Missing parent directories are created automatically."""
    filepath = tmp_path / "deep" / "nested" / "dir" / "output.txt"
    from tinycua.tools.native.files import write_file

    result = write_file(str(filepath), "deep content")
    assert result["success"] is True
    assert filepath.read_text() == "deep content"


def test_write_file_relative_path():
    """Relative path is resolved from TINYCUA_TOOL_ROOT."""
    original_cwd = os.getcwd()
    original_root = os.environ.get("TINYCUA_TOOL_ROOT")
    try:
        with pytest.MonkeyPatch.context() as mp:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                mp.setenv("TINYCUA_TOOL_ROOT", tmpdir)
                os.chdir(tmpdir)
                from tinycua.tools.native.files import write_file

                result = write_file("relative_output.txt", "hello")
                assert result["success"] is True
                assert Path(tmpdir, "relative_output.txt").read_text() == "hello"
    finally:
        os.chdir(original_cwd)
        if original_root is not None:
            os.environ["TINYCUA_TOOL_ROOT"] = original_root
        else:
            os.environ.pop("TINYCUA_TOOL_ROOT", None)


# --- edit_file ---


def test_edit_file_single_line(tmp_path):
    """Replace a single line at a given start position."""
    filepath = tmp_path / "edit.txt"
    filepath.write_text("line 1\nline 2\nline 3\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=2, content="REPLACED", offset=1)
    assert result["success"] is True
    assert result["start_line"] == 2
    assert result["lines_replaced"] == 1
    assert filepath.read_text() == "line 1\nREPLACED\nline 3\n"


def test_edit_file_multiple_lines(tmp_path):
    """Replace multiple lines with offset parameter."""
    filepath = tmp_path / "edit_multi.txt"
    filepath.write_text("line 1\nline 2\nline 3\nline 4\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=2, content="A\nB", offset=2)
    assert result["success"] is True
    assert result["lines_replaced"] == 2
    assert filepath.read_text() == "line 1\nA\nB\nline 4\n"


def test_edit_file_to_end(tmp_path):
    """Replace from start to end of file when offset is None."""
    filepath = tmp_path / "edit_end.txt"
    filepath.write_text("line 1\nline 2\nline 3\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=2, content="TAIL")
    assert result["success"] is True
    assert filepath.read_text() == "line 1\nTAIL"


def test_edit_file_nonexistent_file(tmp_path):
    """Error when editing a file that does not exist."""
    filepath = tmp_path / "does_not_exist.txt"
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=1, content="content")
    assert result["success"] is False
    assert "error" in result


def test_edit_file_invalid_start_line(tmp_path):
    """Error when start line exceeds file length."""
    filepath = tmp_path / "short.txt"
    filepath.write_text("only one line\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=100, content="content")
    assert result["success"] is False
    assert "error" in result
    assert "range" in result.get("error", "").lower()


def test_edit_file_start_plus_offset_exceeds_file(tmp_path):
    """Error when start+offset exceeds file line count."""
    filepath = tmp_path / "short_multi.txt"
    filepath.write_text("line 1\nline 2\nline 3\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=2, content="A\nB\nC\nD\nE", offset=5)
    assert result["success"] is False
    assert "error" in result
    assert "exceeds" in result["error"].lower()


# --- list_files ---


def test_list_files_all(tmp_path):
    """List all files in a directory."""
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()
    (tmp_path / "c.py").touch()
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path))
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(os.path.join(str(tmp_path), f) in result for f in ["a.txt", "b.txt", "c.py"])


def test_list_files_with_pattern(tmp_path):
    """Filter files with a glob pattern."""
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()
    (tmp_path / "c.py").touch()
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path), "*.py")
    assert len(result) == 1
    assert os.path.join(str(tmp_path), "c.py") in result


def test_list_files_directory_not_found(tmp_path):
    """Error dict returned for nonexistent directory."""
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path / "nonexistent_directory_path"))
    assert isinstance(result, dict)
    assert "error" in result


def test_list_files_empty_directory(tmp_path):
    """Empty directory returns empty list."""
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path))
    assert result == []


def test_list_files_relative_path():
    """Relative path is resolved from TINYCUA_TOOL_ROOT."""
    original_cwd = os.getcwd()
    original_root = os.environ.get("TINYCUA_TOOL_ROOT")
    try:
        with pytest.MonkeyPatch.context() as mp:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                mp.setenv("TINYCUA_TOOL_ROOT", tmpdir)
                os.chdir(tmpdir)
                Path("subdir").mkdir()
                Path("subdir", "file.txt").touch()
                from tinycua.tools.native.files import list_files

                result = list_files("subdir")
                assert len(result) == 1
    finally:
        os.chdir(original_cwd)
        if original_root is not None:
            os.environ["TINYCUA_TOOL_ROOT"] = original_root
        else:
            os.environ.pop("TINYCUA_TOOL_ROOT", None)
