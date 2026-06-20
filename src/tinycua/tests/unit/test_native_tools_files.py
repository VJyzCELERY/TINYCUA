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


# --- str_replace edge cases ---


def test_str_replace_exact_match():
    """str_replace replaces exact text match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "exact.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="line 2", new_string="REPLACED")
        assert result["success"] is True
        assert result["replacements_made"] == 1
        content = Path(filepath).read_text()
        assert content == "line 1\nREPLACED\nline 3\n"


def test_str_replace_multiple_matches_error():
    """str_replace with multiple matches and replace_all=False returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "multi.txt")
        Path(filepath).write_text("foo\nbar\nfoo\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="foo", new_string="baz")
        assert result["success"] is False


def test_str_replace_replace_all():
    """str_replace with replace_all=True replaces all occurrences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "all.txt")
        Path(filepath).write_text("foo\nbar\nfoo\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="foo", new_string="baz", replace_all=True)
        assert result["success"] is True
        assert result["replacements_made"] == 2
        assert Path(filepath).read_text() == "baz\nbar\nbaz\n"


def test_str_replace_empty_old_string_creates_file():
    """str_replace with empty old_string creates a new file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "new.txt")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="", new_string="hello world")
        assert result["success"] is True
        assert Path(filepath).read_text() == "hello world"


def test_str_replace_empty_old_string_existing_file_errors():
    """str_replace with empty old_string on existing file returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "exists.txt")
        Path(filepath).write_text("existing content")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="", new_string="new")
        assert result["success"] is False
        assert "write_file" in result["error"]


def test_str_replace_not_found_returns_error():
    """str_replace with old_string not in file returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "notfound.txt")
        Path(filepath).write_text("hello world")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="nonexistent", new_string="x")
        assert result["success"] is False
        assert "Could not find" in result["error"]


def test_str_replace_identical_strings_error():
    """str_replace with identical old and new returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "identical.txt")
        Path(filepath).write_text("hello")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="hello", new_string="hello")
        assert result["success"] is False
        assert "identical" in result["error"]


def test_str_replace_fuzzy_line_trimmed():
    """str_replace matches with trailing whitespace differences (line-trimmed strategy)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "fuzzy.txt")
        Path(filepath).write_text("def foo():\n    pass  \n")
        from tinycua.agent.tools.native.files import str_replace

        # old_string has no trailing spaces, file has trailing spaces on "pass" line
        result = str_replace(filepath, old_string="def foo():\n    pass\n", new_string="def bar():\n    pass\n")
        assert result["success"] is True
        assert "def bar" in Path(filepath).read_text()


def test_str_replace_diff_preview():
    """str_replace returns a diff_preview of the replaced content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "preview.txt")
        Path(filepath).write_text("old text here")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="old", new_string="new")
        assert result["success"] is True
        assert result["diff_preview"] == "new"
        assert "new text here" in Path(filepath).read_text()


# --- append_file edge cases ---


def test_append_file_to_existing():
    """append_file appends content to an existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "append.txt")
        Path(filepath).write_text("line 1\nline 2\n")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="line 3\n")
        assert result["success"] is True
        assert Path(filepath).read_text() == "line 1\nline 2\nline 3\n"


def test_append_file_creates_new():
    """append_file creates a new file if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "new_append.txt")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="new content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "new content"


def test_append_file_adds_newline_separator():
    """append_file adds a newline if the file doesn't end with one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "no_nl.txt")
        Path(filepath).write_text("no newline here")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="appended")
        assert result["success"] is True
        content = Path(filepath).read_text()
        assert content == "no newline here\nappended"


def test_append_file_creates_parent_dirs():
    """append_file creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "subdir", "nested", "file.txt")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="nested content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "nested content"


def test_list_files_no_match():
    """Pattern with no matches returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "readme.md").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir, "*.py")
        assert result == []


def test_list_files_with_subdirectories():
    """list_files lists top-level files and directories (non-recursive).

    Directories appear marked with a trailing ``/`` so the LLM can distinguish
    them from files. Non-recursive means nested entries below the top level are
    not flattened into the result.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "file.txt").touch()
        Path(tmpdir, "subdir").mkdir()
        Path(tmpdir, "subdir", "nested.txt").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        # Top-level only (non-recursive): file.txt and subdir/, not nested.txt.
        assert len(result) == 2
        assert any(p.endswith("file.txt") for p in result)
        assert any(p.endswith("subdir/") for p in result)
        # The nested file is not flattened up to the top level.
        assert not any("nested.txt" in p for p in result)


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


# --- defensive int() coercion for string line args (local models) -------


def test_read_file_accepts_string_start_and_offset():
    """read_file must coerce string line args (local models emit "7")."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "coerce_read.txt")
        Path(filepath).write_text("one\ntwo\nthree\nfour\n")
        from tinycua.agent.tools.native.files import read_file

        result = read_file(filepath, start="2", offset="2")
        assert result == "two\nthree\n"
