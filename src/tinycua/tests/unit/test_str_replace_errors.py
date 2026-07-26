"""Unit tests for str_replace multi-match error distinction (Milestone 8, FR-052)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tinycua.agent.tools.native.context import bind_workspace


class TestStrReplaceMultiMatchError:
    """str_replace distinguishes zero-match from multi-match errors."""

    def test_multi_match_returns_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "multi.txt")
            Path(filepath).write_text("foo\nbar\nfoo\n")
            from tinycua.agent.tools.native.files import str_replace

            result = str_replace(filepath, old_string="foo", new_string="baz")
            assert result["success"] is False
            error = result.get("error", "")
            # FR-052: the error MUST say "Found N matches" with actionable guidance.
            assert "Found" in error
            assert "matches" in error
            assert "replace_all" in error or "more context" in error

    def test_multi_match_replace_all_succeeds(self):
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

    def test_zero_match_returns_could_not_find_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "single.txt")
            Path(filepath).write_text("foo\nbar\n")
            from tinycua.agent.tools.native.files import str_replace

            result = str_replace(filepath, old_string="nonexistent", new_string="x")
            assert result["success"] is False
            error = result.get("error", "")
            # FR-052: zero-match uses the "Could not find" error.
            assert "Could not find" in error
            # And MUST NOT say "Found N matches".
            assert "Found" not in error or "Could not find" in error

    def test_multi_match_error_includes_match_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bind_workspace(tmpdir)
            filepath = os.path.join(tmpdir, "triple.txt")
            Path(filepath).write_text("foo\nfoo\nfoo\n")
            from tinycua.agent.tools.native.files import str_replace

            result = str_replace(filepath, old_string="foo", new_string="baz")
            assert result["success"] is False
            error = result.get("error", "")
            # The error should mention the number of matches found.
            assert "3" in error
