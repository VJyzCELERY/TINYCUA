"""Integration tests for read_file, write_file, str_replace, append_file, list_files tools."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def native_tools_workspace(tmp_path, monkeypatch):
    """Bind each test's temporary files to an isolated native-tools workspace."""
    from tinycua.agent.tools.native.context import bind_file_execution, bind_workspace

    original_chdir = os.chdir

    def chdir(path):
        original_chdir(path)
        target = Path(path).resolve()
        bind_workspace(target if target.is_relative_to(tmp_path) else tmp_path)

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(os, "chdir", chdir)
    bind_workspace(tmp_path)
    bind_file_execution("integration-test")
    yield
    bind_file_execution(None)
    bind_workspace(None)


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

    result = read_file("missing.txt")
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
        from tinycua.agent.tools.native.files import read_file, write_file

        assert read_file(filepath) == "old content"
        result = write_file(filepath, "new content", replace=True)
        assert result["success"] is True
        assert Path(filepath).read_text() == "new content"


def test_existing_public_mutations_require_a_current_read():
    """Public mutation tools reject an unobserved existing revision."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "existing.txt")
        Path(filepath).write_text("old content")
        from tinycua.agent.tools.native.files import append_file, str_replace, write_file

        results = [
            write_file(filepath, "new content", replace=True),
            str_replace(filepath, old_string="old", new_string="new"),
            append_file(filepath, content="appended"),
        ]

        assert all(result["success"] is False for result in results)
        assert all("read" in result["error"].lower() for result in results)
        assert Path(filepath).read_text() == "old content"


def test_write_file_rejects_missing_parent_dirs():
    """Missing parent directories cause a failure without filesystem changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir, "deep/nested/dir")
        filepath = parent / "output.txt"
        from tinycua.agent.tools.native.files import write_file

        result = write_file(str(filepath), "deep content")

        assert result["success"] is False
        assert result["path"] == str(filepath)
        assert result["chars_written"] == 0
        assert "parent directory does not exist" in result["error"].lower()
        assert not parent.exists()
        assert not filepath.exists()


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
        from tinycua.agent.tools.native.files import read_file, str_replace

        assert read_file(filepath) == "line 1\nline 2\nline 3\n"
        result = str_replace(filepath, old_string="line 2", new_string="REPLACED")
        assert result["success"] is True
        assert result["replacements_made"] == 1
        assert Path(filepath).read_text() == "line 1\nREPLACED\nline 3\n"


def test_str_replace_multiple_lines():
    """Replace multiple lines by content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "replace_multi.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\nline 4\n")
        from tinycua.agent.tools.native.files import read_file, str_replace

        assert read_file(filepath) == "line 1\nline 2\nline 3\nline 4\n"
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
        from tinycua.agent.tools.native.files import read_file, str_replace

        assert read_file(filepath) == "    def foo():\n        return 42\n"
        # old_string with different indentation than the file
        result = str_replace(
            filepath,
            old_string="def foo():\n  return 42",
            new_string="def bar():\n  return 0",
        )
        assert result["success"] is True
        content = Path(filepath).read_text()
        assert "def bar" in content


# --- append_file ---


def test_append_file_to_existing():
    """Append content to an existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "append.txt")
        Path(filepath).write_text("original\n")
        from tinycua.agent.tools.native.files import append_file, read_file

        assert read_file(filepath) == "original\n"
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
            str(Path(tmpdir).relative_to(tempfile.tempdir) / f) in result
            for f in ["a.txt", "b.txt", "c.py"]
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
        assert str(Path(tmpdir).relative_to(tempfile.tempdir) / "c.py") in result


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


# --- search_files ---


def test_search_files_multiple_files():
    """Search across multiple files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "a.py").write_text("def hello():\n    pass\n")
        Path(tmpdir, "b.py").write_text("hello = 'world'\n")
        Path(tmpdir, "c.txt").write_text("not a match\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("hello", path=tmpdir, file_glob="*.py")
        assert isinstance(result, list)
        assert len(result) >= 2
        assert any("a.py" in r for r in result)
        assert any("b.py" in r for r in result)


def test_search_files_recursive():
    """Search recursively through subdirectories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "top.py").write_text("target_function\n")
        Path(tmpdir, "subdir").mkdir()
        Path(tmpdir, "subdir", "nested.py").write_text("target_function\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("target_function", path=tmpdir)
        assert isinstance(result, list)
        assert len(result) >= 2
        assert any("top.py" in r for r in result)
        assert any("nested.py" in r for r in result)
