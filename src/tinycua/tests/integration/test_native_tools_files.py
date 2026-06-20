"""Integration tests for read_file, write_file, str_replace, append_file, list_files tools."""

import os
import tempfile
from pathlib import Path


# --- read_file ---


def test_read_file_full():
    """Read entire file when start and offset are not set."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert result == "line 1\nline 2\nline 3\n"
    finally:
        os.unlink(path)


def test_read_file_start_only():
    """Read from start line to end of file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\nline 4\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=2)
        assert result == "line 2\nline 3\nline 4\n"
    finally:
        os.unlink(path)


def test_read_file_start_and_offset():
    """Read exactly offset lines from start."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\nline 4\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=2, offset=2)
        assert result == "line 2\nline 3\n"
    finally:
        os.unlink(path)


def test_read_file_start_plus_offset_exceeds_file():
    """Error when start+offset exceeds file line count."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=2, offset=5)
        assert isinstance(result, dict)
        assert "error" in result
        assert "exceeds" in result["error"].lower()
    finally:
        os.unlink(path)


def test_read_file_truncation():
    """Full-file read truncates when file exceeds internal limit."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        # Write ~150KB to exceed 100KB limit
        f.write("x" * 150 * 1024)
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert "[Truncated:" in result
    finally:
        os.unlink(path)


def test_read_file_range_no_truncation():
    """Range reads bypass truncation limit entirely."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("x" * 150 * 1024)
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        # Read first 5 lines — should NOT be truncated even though file > 100KB
        result = read_file(path, start=1, offset=5)
        assert "[Truncated:" not in result
    finally:
        os.unlink(path)


def test_read_file_not_found():
    """Error dict returned for missing file."""
    from tinycua.agent.tools.native.files import read_file

    result = read_file("/nonexistent/path/file.txt")
    assert isinstance(result, dict)
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_read_file_invalid_start_line():
    """Error dict returned when start exceeds file length."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("only one line\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=100)
        assert isinstance(result, dict)
        assert "error" in result
        assert "range" in result["error"].lower()
    finally:
        os.unlink(path)


def test_read_file_empty():
    """Read an empty file returns empty string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name  # write nothing
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert result == ""
    finally:
        os.unlink(path)


def test_read_file_relative_path():
    """Relative path is resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path("test.txt").write_text("hello world\n")

            from tinycua.agent.tools.native.files import read_file

            result = read_file("test.txt")
            assert result == "hello world\n"
    finally:
        os.chdir(original_cwd)


# --- write_file ---


def test_write_file_create():
    """Create a new file with content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "output.txt")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "hello world")
        assert result["success"] is True
        assert result["path"] == filepath
        assert result["chars_written"] == len("hello world")
        assert Path(filepath).read_text() == "hello world"


def test_write_file_overwrite():
    """Overwrite an existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "existing.txt")
        Path(filepath).write_text("old content")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "new content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "new content"


def test_write_file_creates_parent_dirs():
    """Missing parent directories are created automatically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "deep/nested/dir/output.txt")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "deep content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "deep content"


def test_write_file_relative_path():
    """Relative path is resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from tinycua.agent.tools.native.files import write_file

            result = write_file("relative_output.txt", "hello")
            assert result["success"] is True
            assert Path(tmpdir, "relative_output.txt").read_text() == "hello"
    finally:
        os.chdir(original_cwd)


# --- str_replace ---


def test_str_replace_single_line():
    """Replace a single line by content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "replace.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="line 2", new_string="REPLACED")
        assert result["success"] is True
        assert result["replacements_made"] == 1
        assert Path(filepath).read_text() == "line 1\nREPLACED\nline 3\n"


def test_str_replace_multiple_lines():
    """Replace multiple lines by content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "replace_multi.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\nline 4\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="line 2\nline 3", new_string="A\nB")
        assert result["success"] is True
        assert Path(filepath).read_text() == "line 1\nA\nB\nline 4\n"


def test_str_replace_nonexistent_file():
    """Error when replacing in a file that does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "does_not_exist.txt")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="x", new_string="y")
        assert result["success"] is False
        assert "error" in result


def test_str_replace_creates_file_with_empty_old():
    """str_replace with empty old_string creates a new file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "created.txt")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="", new_string="new file content\n")
        assert result["success"] is True
        assert Path(filepath).read_text() == "new file content\n"


def test_str_replace_fuzzy_whitespace():
    """str_replace matches despite whitespace differences (fuzzy strategy)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "fuzzy.txt")
        Path(filepath).write_text("    def foo():\n        return 42\n")
        from tinycua.agent.tools.native.files import str_replace

        # old_string with different indentation than the file
        result = str_replace(filepath, old_string="def foo():\n  return 42", new_string="def bar():\n  return 0")
        assert result["success"] is True
        content = Path(filepath).read_text()
        assert "def bar" in content


# --- append_file ---


def test_append_file_to_existing():
    """Append content to an existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "append.txt")
        Path(filepath).write_text("original\n")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="appended\n")
        assert result["success"] is True
        assert Path(filepath).read_text() == "original\nappended\n"


def test_append_file_creates_new():
    """Append creates a new file if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "new_append.txt")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="brand new\n")
        assert result["success"] is True
        assert Path(filepath).read_text() == "brand new\n"


# --- list_files ---


def test_list_files_all():
    """List all files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "a.txt").touch()
        Path(tmpdir, "b.txt").touch()
        Path(tmpdir, "c.py").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(
            os.path.join(tmpdir, f) in result for f in ["a.txt", "b.txt", "c.py"]
        )


def test_list_files_with_pattern():
    """Filter files with a glob pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "a.txt").touch()
        Path(tmpdir, "b.txt").touch()
        Path(tmpdir, "c.py").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir, "*.py")
        assert len(result) == 1
        assert os.path.join(tmpdir, "c.py") in result


def test_list_files_directory_not_found():
    """Error dict returned for nonexistent directory."""
    from tinycua.agent.tools.native.files import list_files

    result = list_files("/nonexistent/path")
    assert isinstance(result, dict)
    assert "error" in result


def test_list_files_empty_directory():
    """Empty directory returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        assert result == []


def test_list_files_relative_path():
    """Relative path is resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path("subdir").mkdir()
            Path("subdir", "file.txt").touch()
            from tinycua.agent.tools.native.files import list_files

            result = list_files("subdir")
            assert len(result) == 1
    finally:
        os.chdir(original_cwd)


def test_list_files_includes_hidden_files_and_directories():
    """list_files lists both files and directories, including dotfile entries.

    Hidden entries (``.venv``, ``.hidden.txt``) must appear alongside visible
    ones so a reviewer/executor can see created workspace artifacts. Directories
    are marked with a trailing ``/`` so the LLM can distinguish them from files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "visible.txt").touch()
        Path(tmpdir, ".hidden.txt").touch()
        Path(tmpdir, ".venv").mkdir()
        Path(tmpdir, "subdir").mkdir()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)

        assert isinstance(result, list)
        # Compare on the basename portion; directories carry a trailing "/" marker.
        names = [entry.rstrip("/").rsplit("/", 1)[-1] for entry in result]
        # Hidden files appear
        assert ".hidden.txt" in names
        assert "visible.txt" in names
        # Directories appear (and the raw entry is suffixed with "/")
        assert ".venv" in names
        assert "subdir" in names
        assert any(entry.endswith("/.venv/") for entry in result)
        assert any(entry.endswith("/subdir/") for entry in result)


def test_list_files_traverses_into_subdirectory_path():
    """list_files accepts a path to any directory inside the workspace, not just
    the workspace root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "outer").mkdir()
        Path(tmpdir, "outer", "inner.txt").touch()
        Path(tmpdir, "outer", "nested_dir").mkdir()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(f"{tmpdir}/outer")

        names = [entry.rstrip("/").rsplit("/", 1)[-1] for entry in result]
        assert "inner.txt" in names
        assert "nested_dir" in names
        assert any(entry.endswith("/nested_dir/") for entry in result)


def test_list_files_default_pattern_still_filters_by_extension():
    """The pattern kwarg still filters; directories matching the pattern appear
    too so the LLM isn't blind to structure when filtering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "a.txt").touch()
        Path(tmpdir, "b.py").touch()
        Path(tmpdir, "src").mkdir()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir, "*.py")
        names = [Path(entry).name for entry in result]
        assert "b.py" in names
