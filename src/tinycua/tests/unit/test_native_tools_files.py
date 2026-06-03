"""Unit tests for files.py — testing path resolution, edge cases."""

import os
import tempfile
from pathlib import Path

import pytest


# --- read_file edge cases ---


def test_read_file_path_resolution_absolute():
    """Absolute paths are used as-is."""
    from tinycua.tools.native.files import read_file

    result = read_file("/tmp/nonexistent_absolute_path.txt")
    assert isinstance(result, dict)
    assert "error" in result


def test_read_file_path_resolution_relative():
    """Relative paths are resolved from TINYCUA_TOOL_ROOT."""
    original_cwd = os.getcwd()
    original_root = os.environ.get("TINYCUA_TOOL_ROOT")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["TINYCUA_TOOL_ROOT"] = tmpdir
            os.chdir(tmpdir)
            Path("subdir").mkdir()
            Path("subdir/test.txt").write_text("relative content\n")

            from tinycua.tools.native.files import read_file

            result = read_file("subdir/test.txt")
            assert result == "relative content\n"
    finally:
        os.chdir(original_cwd)
        if original_root is not None:
            os.environ["TINYCUA_TOOL_ROOT"] = original_root
        else:
            os.environ.pop("TINYCUA_TOOL_ROOT", None)


def test_read_file_dot_slash_prefix():
    """Paths with ./ prefix are treated as relative."""
    original_cwd = os.getcwd()
    original_root = os.environ.get("TINYCUA_TOOL_ROOT")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["TINYCUA_TOOL_ROOT"] = tmpdir
            os.chdir(tmpdir)
            Path("dotfile.txt").write_text("dot content\n")

            from tinycua.tools.native.files import read_file

            result = read_file("./dotfile.txt")
            assert result == "dot content\n"
    finally:
        os.chdir(original_cwd)
        if original_root is not None:
            os.environ["TINYCUA_TOOL_ROOT"] = original_root
        else:
            os.environ.pop("TINYCUA_TOOL_ROOT", None)


def test_read_file_permission_denied(tmp_path):
    """Permission denied returns error dict (skip on Windows)."""
    import platform
    if platform.system() == "Windows":
        pytest.skip("Permission tests not supported on Windows")

    from tinycua.tools.native.files import read_file

    filepath = tmp_path / "secret.txt"
    filepath.write_bytes(b"secret\n")
    os.chmod(filepath, 0o000)  # Remove all permissions
    try:
        result = read_file(str(filepath))
        assert isinstance(result, dict)
        assert "error" in result
        assert "permission" in result["error"].lower() or "denied" in result["error"].lower()
    finally:
        os.chmod(filepath, 0o644)  # Restore for cleanup


def test_read_file_not_a_file():
    """Reading a directory returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from tinycua.tools.native.files import read_file
        result = read_file(tmpdir)
        assert isinstance(result, dict)
        assert "error" in result


def test_read_file_start_zero_returns_error(tmp_path):
    """start=0 (invalid, must be >= 1) returns error."""
    from tinycua.tools.native.files import read_file

    filepath = tmp_path / "start_zero.txt"
    filepath.write_text("hello\nworld\n")
    result = read_file(str(filepath), start=0)
    assert isinstance(result, dict)
    assert "error" in result
    assert "Invalid start line" in result["error"]


def test_read_file_truncation_message_format(tmp_path):
    """Truncation message matches expected format with resume hint."""
    filepath = tmp_path / "large.txt"
    filepath.write_text("x" * 150 * 1024)
    from tinycua.tools.native.files import read_file

    result = read_file(str(filepath))
    assert "[Truncated:" in result
    assert "lines remaining" in result
    assert "bytes not shown" in result
    assert "Set start=" in result


# --- write_file edge cases ---


def test_write_file_empty_content(tmp_path):
    """Writing empty content creates empty file."""
    filepath = tmp_path / "empty.txt"
    from tinycua.tools.native.files import write_file

    result = write_file(str(filepath), "")
    assert result["success"] is True
    assert result["chars_written"] == 0
    assert filepath.read_text() == ""


def test_write_file_binary_content(tmp_path):
    """Writing text with binary-looking content works."""
    filepath = tmp_path / "binary.txt"
    from tinycua.tools.native.files import write_file

    content = "hello\x00world\x01test"
    result = write_file(str(filepath), content)
    assert result["success"] is True
    assert filepath.read_bytes() == content.encode("utf-8")


# --- edit_file edge cases ---


def test_edit_file_with_newline_content(tmp_path):
    """Editing with content that ends with newline is handled."""
    filepath = tmp_path / "edit_nl.txt"
    filepath.write_text("line 1\nline 2\nline 3\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=2, content="A\nB\n", offset=2)
    assert result["success"] is True
    assert result["lines_replaced"] == 2
    content = filepath.read_text()
    # The replacement content's trailing newline should be respected
    assert "A\nB\n" in content


def test_edit_file_start_zero_returns_error(tmp_path):
    """edit_file with start=0 (invalid, must be >= 1) returns error."""
    filepath = tmp_path / "edit_start_zero.txt"
    filepath.write_text("line 1\nline 2\n")
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=0, content="new")
    assert result["success"] is False
    assert "Invalid start line" in result["error"]


def test_edit_file_single_line_no_trailing_newline(tmp_path):
    """edit_file on a file without trailing newline."""
    filepath = tmp_path / "no_nl.txt"
    filepath.write_text("line 1\nline 2")  # no trailing newline
    from tinycua.tools.native.files import edit_file

    result = edit_file(str(filepath), start=2, content="REPLACED")
    assert result["success"] is True
    result_text = filepath.read_text()
    assert result_text == "line 1\nREPLACED"


# --- list_files edge cases ---


def test_list_files_no_match(tmp_path):
    """Pattern with no matches returns empty list."""
    (tmp_path / "readme.md").touch()
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path), "*.py")
    assert result == []


def test_list_files_with_subdirectories(tmp_path):
    """list_files only returns files at the top level (non-recursive)."""
    (tmp_path / "file.txt").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").touch()
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path))
    # Only top-level files, not recursive
    assert len(result) == 1
    assert any(p.endswith("file.txt") for p in result)


def test_list_files_on_file_returns_error(tmp_path):
    """list_files on a file path (not a directory) returns error."""
    filepath = tmp_path / "not_a_dir.txt"
    filepath.write_bytes(b"content")
    from tinycua.tools.native.files import list_files

    result = list_files(str(filepath))
    assert isinstance(result, dict)
    assert "error" in result
    assert "Not a directory" in result["error"]


def test_list_files_absolute_paths(tmp_path):
    """Returned paths are absolute."""
    (tmp_path / "test.txt").touch()
    from tinycua.tools.native.files import list_files

    result = list_files(str(tmp_path))
    assert len(result) == 1
    assert Path(result[0]).is_absolute()


# --- Sandbox escape regression tests ---


@pytest.fixture(autouse=False)
def _sandbox_root(tmp_path):
    """Set TINYCUA_TOOL_ROOT to a narrow tmp_path for sandbox tests."""
    original = os.environ.get("TINYCUA_TOOL_ROOT")
    os.environ["TINYCUA_TOOL_ROOT"] = str(tmp_path)
    yield tmp_path
    if original is not None:
        os.environ["TINYCUA_TOOL_ROOT"] = original
    else:
        os.environ.pop("TINYCUA_TOOL_ROOT", None)


@pytest.mark.usefixtures("_sandbox_root")
class TestSandboxEscape:
    """Verify that file tools reject paths escaping TINYCUA_TOOL_ROOT."""

    def test_read_file_relative_traversal(self, _sandbox_root):
        """read_file with ../outside.txt is rejected."""
        from tinycua.tools.native.files import read_file

        result = read_file("../outside.txt")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_read_file_absolute_outside_root(self, _sandbox_root):
        """read_file with an absolute path outside the sandbox is rejected."""
        from tinycua.tools.native.files import read_file

        result = read_file("/etc/passwd")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_write_file_relative_traversal(self, _sandbox_root):
        """write_file with ../outside.txt is rejected."""
        from tinycua.tools.native.files import write_file

        result = write_file("../outside.txt", "content")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_write_file_absolute_outside_root(self, _sandbox_root):
        """write_file with an absolute path outside the sandbox is rejected."""
        from tinycua.tools.native.files import write_file

        result = write_file("/tmp/outside.txt", "content")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_edit_file_relative_traversal(self, _sandbox_root):
        """edit_file with ../outside.txt is rejected."""
        from tinycua.tools.native.files import edit_file

        result = edit_file("../outside.txt", start=1, content="new")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_edit_file_absolute_outside_root(self, _sandbox_root):
        """edit_file with an absolute path outside the sandbox is rejected."""
        from tinycua.tools.native.files import edit_file

        result = edit_file("/tmp/outside.txt", start=1, content="new")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_list_files_relative_traversal(self, _sandbox_root):
        """list_files with ../outside/ is rejected."""
        from tinycua.tools.native.files import list_files

        result = list_files("../")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")

    def test_list_files_absolute_outside_root(self, _sandbox_root):
        """list_files with an absolute path outside the sandbox is rejected."""
        from tinycua.tools.native.files import list_files

        result = list_files("/tmp")
        assert isinstance(result, dict)
        assert "escapes tool root" in result.get("error", "")
