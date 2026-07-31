"""Unit tests for files.py — testing path resolution, edge cases."""

import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from tinycua.agent.tools.native.context import bind_managed_draft_dir, bind_workspace


# --- read_file edge cases ---


def test_managed_drafts_are_hidden_without_node_ownership(tmp_path: Path) -> None:
    """Normal workspace inspection cannot expose another node's managed draft."""
    from tinycua.agent.tools.native.files import list_files, read_file

    draft_dir = tmp_path / ".tinycua" / "session" / "tmp" / "execution"
    draft_dir.mkdir(parents=True)
    (draft_dir / "draft.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("visible\n", encoding="utf-8")
    bind_workspace(tmp_path)

    assert list_files() == ["visible.txt"]
    assert read_file(".tinycua/session/tmp/execution/draft.json") == {
        "error": "Managed drafts are unavailable to this node."
    }

    bind_managed_draft_dir(draft_dir)
    assert read_file(".tinycua/session/tmp/execution/draft.json") == "{}\n"


def test_read_file_returns_a_model_attachment_for_png(tmp_path: Path) -> None:
    """A workspace image is returned as an attachment, not decoded text."""
    from tinycua.agent.tools.native.files import read_file

    image_path = tmp_path / "diagram.png"
    Image.new("RGB", (2, 3), "red").save(image_path)
    bind_workspace(tmp_path)

    result = read_file("diagram.png")

    assert isinstance(result, dict)
    assert result["image_metadata"] == {
        "path": "diagram.png",
        "mime_type": "image/png",
        "width": 2,
        "height": 3,
        "bytes": image_path.stat().st_size,
    }
    assert result["attachments"][0].mime_type == "image/png"
    assert "base64" not in result["content"]


def test_read_file_rejects_line_ranges_for_images(tmp_path: Path) -> None:
    """Text line ranges cannot be applied to binary images."""
    from tinycua.agent.tools.native.files import read_file

    Image.new("RGB", (1, 1)).save(tmp_path / "diagram.png")
    bind_workspace(tmp_path)

    assert read_file("diagram.png", start=1) == {
        "error": "Line ranges are not supported for images."
    }


def test_read_file_path_resolution_absolute():
    """Absolute paths outside workspace raise an error (workspace must be bound)."""
    from tinycua.agent.tools.native.context import bind_workspace
    from tinycua.agent.tools.native.files import read_file

    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        result = read_file("/nonexistent/absolute/path.txt")
        assert isinstance(result, dict)
        assert "error" in result


def test_read_file_path_resolution_relative():
    """Relative paths are resolved from the bound workspace."""
    from tinycua.agent.tools.native.context import bind_workspace

    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "subdir").mkdir()
        Path(tmpdir, "subdir/test.txt").write_text("relative content\n")

        from tinycua.agent.tools.native.files import read_file

        result = read_file("subdir/test.txt")
        assert result == "relative content\n"


def test_read_file_dot_slash_prefix():
    """Paths with ./ prefix are treated as relative to the workspace."""
    from tinycua.agent.tools.native.context import bind_workspace

    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "dotfile.txt").write_text("dot content\n")

        from tinycua.agent.tools.native.files import read_file

        result = read_file("./dotfile.txt")
        assert result == "dot content\n"


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
        bind_workspace(tempfile.gettempdir())  # bind workspace to temp dir
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
        bind_workspace(tmpdir)
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
        bind_workspace(tempfile.gettempdir())
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

        bind_workspace(tempfile.gettempdir())
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
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "empty.txt")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "")
        assert result["success"] is True
        assert result["chars_written"] == 0
        assert Path(filepath).read_text() == ""


def test_write_file_binary_content():
    """Writing text with binary-looking content works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "binary.txt")
        from tinycua.agent.tools.native.files import write_file

        content = "hello\x00world\x01test"
        result = write_file(filepath, content)
        assert result["success"] is True
        assert Path(filepath).read_bytes() == content.encode("utf-8")


def test_file_mutations_preserve_exact_decoded_content():
    """File mutation tools persist decoded content without reinterpretation."""
    content = (
        'python = "\\n"\n'
        'regex = r"\\t\\w+"\n'
        'json = "{\\"escape\\": \\"\\\\u2208\\"}"\n'
        'latex = r"\\text{value}"\n'
        "tab =\tvalue\ncarriage =\rvalue\nunicode = ∈"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        from tinycua.agent.tools.native.files import (
            append_file,
            str_replace,
            write_file,
        )

        write_path = Path(tmpdir, "write.txt")
        assert write_file(str(write_path), content)["success"] is True
        assert write_path.read_bytes() == content.encode("utf-8")

        replace_path = Path(tmpdir, "replace.txt")
        replace_path.write_text("replace me", encoding="utf-8")
        assert str_replace(str(replace_path), "replace me", content)["success"] is True
        assert replace_path.read_bytes() == content.encode("utf-8")

        append_path = Path(tmpdir, "append.txt")
        assert append_file(str(append_path), content)["success"] is True
        assert append_path.read_bytes() == content.encode("utf-8")


# --- str_replace edge cases ---


def test_str_replace_exact_match():
    """str_replace replaces exact text match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
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
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "multi.txt")
        Path(filepath).write_text("foo\nbar\nfoo\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="foo", new_string="baz")
        assert result["success"] is False


def test_str_replace_replace_all():
    """str_replace with replace_all=True replaces all occurrences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "all.txt")
        Path(filepath).write_text("foo\nbar\nfoo\n")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(
            filepath, old_string="foo", new_string="baz", replace_all=True
        )
        assert result["success"] is True
        assert result["replacements_made"] == 2
        assert Path(filepath).read_text() == "baz\nbar\nbaz\n"


def test_str_replace_empty_old_string_creates_file():
    """str_replace with empty old_string creates a new file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "new.txt")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="", new_string="hello world")
        assert result["success"] is True
        assert Path(filepath).read_text() == "hello world"


def test_str_replace_empty_old_string_existing_file_errors():
    """str_replace with empty old_string on existing file returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "exists.txt")
        Path(filepath).write_text("existing content")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="", new_string="new")
        assert result["success"] is False
        assert "write_file" in result["error"]


def test_str_replace_not_found_returns_error():
    """str_replace with old_string not in file returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "notfound.txt")
        Path(filepath).write_text("hello world")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="nonexistent", new_string="x")
        assert result["success"] is False
        assert "Could not find" in result["error"]


def test_str_replace_identical_strings_error():
    """str_replace with identical old and new returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "identical.txt")
        Path(filepath).write_text("hello")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="hello", new_string="hello")
        assert result["success"] is False
        assert "identical" in result["error"]


def test_str_replace_fuzzy_line_trimmed():
    """str_replace matches with trailing whitespace differences (line-trimmed strategy)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "fuzzy.txt")
        Path(filepath).write_text("def foo():\n    pass  \n")
        from tinycua.agent.tools.native.files import str_replace

        # old_string has no trailing spaces, file has trailing spaces on "pass" line
        result = str_replace(
            filepath,
            old_string="def foo():\n    pass\n",
            new_string="def bar():\n    pass\n",
        )
        assert result["success"] is True
        assert "def bar" in Path(filepath).read_text()


def test_str_replace_diff_preview():
    """str_replace returns a unified-diff preview of the replaced content (FR-058)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "preview.txt")
        Path(filepath).write_text("old text here")
        from tinycua.agent.tools.native.files import str_replace

        result = str_replace(filepath, old_string="old", new_string="new")
        assert result["success"] is True
        # FR-058: diff_preview is now a unified-diff snippet, not just new_string.
        assert "new" in result["diff_preview"]
        assert "new text here" in Path(filepath).read_text()


# --- append_file edge cases ---


def test_append_file_to_existing():
    """append_file appends content to an existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "append.txt")
        Path(filepath).write_text("line 1\nline 2\n")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="line 3\n")
        assert result["success"] is True
        assert Path(filepath).read_text() == "line 1\nline 2\nline 3\n"


def test_append_file_creates_new():
    """append_file creates a new file if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "new_append.txt")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="new content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "new content"


def test_append_file_adds_newline_separator():
    """append_file adds a newline if the file doesn't end with one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
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
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "subdir", "nested", "file.txt")
        from tinycua.agent.tools.native.files import append_file

        result = append_file(filepath, content="nested content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "nested content"


def test_list_files_no_match():
    """Pattern with no matches returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
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
        bind_workspace(tmpdir)
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

        bind_workspace(tempfile.gettempdir())
        result = list_files(path)
        assert isinstance(result, dict)
        assert "error" in result
        assert "Not a directory" in result["error"]
    finally:
        os.unlink(path)


def test_list_files_absolute_paths():
    """Returned paths are workspace-relative (FR-035: relative, not absolute)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "test.txt").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        assert len(result) == 1
        # FR-035: list_files now returns workspace-relative paths.
        assert result[0] == "test.txt"


# --- defensive int() coercion for string line args (local models) -------


def test_read_file_accepts_string_start_and_offset():
    """read_file must coerce string line args (local models emit "7")."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "coerce_read.txt")
        Path(filepath).write_text("one\ntwo\nthree\nfour\n")
        from tinycua.agent.tools.native.files import read_file

        result = read_file(filepath, start="2", offset="2")
        assert result == "two\nthree\n"


# --- read_file literal \\n warning ---


def test_read_file_warns_about_literal_backslash_n_on_long_lines():
    """read_file appends a warning when a long line has literal \\n."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "malformed.txt")
        # Write a file with a long line containing literal \n (backslash + n)
        long_content = "x" * 600 + "\\n" + "y" * 100
        Path(filepath).write_text(long_content)
        from tinycua.agent.tools.native.files import read_file

        result = read_file(filepath)
        assert "Warning" in result
        assert "literal" in result.lower()
        assert "inspect the expected file format" in result.lower()
        assert "str_replace" not in result


def test_read_file_no_warning_for_short_literal_backslash_n():
    """read_file does not warn for short lines with literal \\n."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "short.txt")
        Path(filepath).write_text('sep = "\\n"')
        from tinycua.agent.tools.native.files import read_file

        result = read_file(filepath)
        assert "Warning" not in result


# --- search_files ---


def test_search_files_content_exact():
    """search_files finds exact string in file content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "test.py")
        Path(filepath).write_text("def foo():\n    return 42\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("foo", path=tmpdir)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any("foo" in r for r in result)


def test_search_files_content_regex():
    """search_files finds regex pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "test.py")
        Path(filepath).write_text("val = 12345\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files(r"\d+", path=tmpdir)
        assert isinstance(result, list)
        assert any("12345" in r for r in result)


def test_search_files_files_only():
    """search_files target='files' finds files by glob."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "a.py").touch()
        Path(tmpdir, "b.txt").touch()
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("*.py", target="files", path=tmpdir)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].endswith("a.py")


def test_search_files_file_glob_filter():
    """search_files filters by file_glob in content mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "match.py").write_text("target_string\n")
        Path(tmpdir, "skip.txt").write_text("target_string\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("target_string", path=tmpdir, file_glob="*.py")
        assert isinstance(result, list)
        assert len(result) == 1
        assert "match.py" in result[0]


def test_search_files_context_lines():
    """search_files returns context lines around matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        filepath = os.path.join(tmpdir, "ctx.py")
        Path(filepath).write_text("line1\nline2\nMATCH\nline4\nline5\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("MATCH", path=tmpdir, context=1)
        assert isinstance(result, list)
        # Should include line before, match, and line after
        assert any("line2" in r for r in result)
        assert any("MATCH" in r for r in result)
        assert any("line4" in r for r in result)


def test_search_files_output_mode_count():
    """search_files count mode returns match counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "multi.py").write_text("foo\nfoo\nbar\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("foo", path=tmpdir, output_mode="count")
        assert isinstance(result, list)
        assert any("2 matches" in r for r in result)


def test_search_files_no_matches():
    """search_files returns 'No matches found' for no matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "empty.py").write_text("nothing here\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("nonexistent_pattern", path=tmpdir)
        assert isinstance(result, list)
        assert result == ["No matches found."]


def test_search_files_nonexistent_path():
    """search_files returns error for nonexistent path."""
    import tinycua.agent.tools.native.files as files_mod

    files_mod._last_search_key = None
    files_mod._search_repeat_count = 0
    from tinycua.agent.tools.native.files import search_files

    bind_workspace(tempfile.gettempdir())
    result = search_files("test", path="/nonexistent/path/xyz")
    assert isinstance(result, dict)
    assert "error" in result


def test_search_files_loop_detection():
    """search_files blocks after 4 identical consecutive searches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "loop.py").write_text("test content\n")
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        # First 3 calls should succeed
        for _ in range(3):
            result = search_files("test", path=tmpdir)
            assert isinstance(result, list)

        # 4th call should be blocked
        result = search_files("test", path=tmpdir)
        assert isinstance(result, dict)
        assert result.get("blocked") is True


def test_search_files_pagination():
    """search_files pagination via offset and limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bind_workspace(tmpdir)
        Path(tmpdir, "page.py").write_text(
            "\n".join(f"match_{i}" for i in range(10)) + "\n"
        )
        import tinycua.agent.tools.native.files as files_mod

        files_mod._last_search_key = None
        files_mod._search_repeat_count = 0
        from tinycua.agent.tools.native.files import search_files

        result = search_files("match_", path=tmpdir, limit=3, offset=0)
        assert isinstance(result, list)
        assert len(result) <= 4  # 3 results + possibly truncation notice
