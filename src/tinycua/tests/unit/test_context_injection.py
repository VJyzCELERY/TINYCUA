"""Unit tests for context injection in native tools.

Tests that native tools (shell, files, web, python_exec) correctly use
ExecutorContext for configurable timeouts, file size limits, feature flags,
and other shared configuration.
"""

from __future__ import annotations



# ---------------------------------------------------------------------------
# Shell tool context injection
# ---------------------------------------------------------------------------


class TestShellContextInjection:
    """Tests for run_shell context injection."""

    def test_shell_respects_context_timeout(self):
        """run_shell should clamp timeout to context's shell_timeout."""
        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext
        from tinycua.agent.tools import register_all

        config = ExecutorConfig(shell_timeout=1)
        ctx = ExecutorContext(config=config)
        tools = register_all(context=ctx)
        shell_tool = next(t for t in tools if t.name == "run_shell")

        result = shell_tool(command="sleep 10", timeout=30)
        assert result["timed_out"] is True
        assert result["exit_code"] == -1

    def test_shell_no_context_uses_default_timeout(self):
        """Without context, run_shell uses its default timeout parameter."""
        from tinycua.agent.tools.native.shell import run_shell

        # This should work normally with default timeout
        result = run_shell(command="echo hello")
        assert "hello" in result["stdout"]
        assert result["exit_code"] == 0

    def test_shell_short_timeout_not_clamped(self):
        """When explicit timeout is below context max, it's not clamped up."""
        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext
        from tinycua.agent.tools import register_all

        config = ExecutorConfig(shell_timeout=30)
        ctx = ExecutorContext(config=config)
        tools = register_all(context=ctx)
        shell_tool = next(t for t in tools if t.name == "run_shell")

        result = shell_tool(command="sleep 10", timeout=1)
        assert result["timed_out"] is True


# ---------------------------------------------------------------------------
# File tool context injection
# ---------------------------------------------------------------------------


class TestFilesContextInjection:
    """Tests for file tools context injection."""

    def test_write_file_default_allowed_paths(self):
        """Without context, write_file should work anywhere."""
        import tempfile
        from pathlib import Path

        from tinycua.agent.tools.native.files import write_file

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            result = write_file(str(test_file), "hello")
            assert result["success"] is True

    def test_write_file_respects_allowed_paths(self):
        """With context and allowed_paths, writing outside should fail."""
        import tempfile
        from pathlib import Path

        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext
        from tinycua.agent.tools import register_all

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed = Path(tmpdir) / "allowed"
            allowed.mkdir()

            config = ExecutorConfig(allowed_paths=[str(allowed)])
            ctx = ExecutorContext(config=config)
            tools = register_all(context=ctx)
            write_tool = next(t for t in tools if t.name == "write_file")

            # Writing inside allowed path should work
            inside = allowed / "good.txt"
            result = write_tool(path=str(inside), content="ok")
            assert result["success"] is True

            # Writing outside allowed path should fail
            outside = Path(tmpdir) / "bad.txt"
            result = write_tool(path=str(outside), content="not ok")
            assert "error" in result

    def test_read_file_truncation_with_context(self):
        """read_file should use context's max_file_size."""
        import tempfile
        from pathlib import Path

        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext
        from tinycua.agent.tools import register_all

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "large.txt"
            # Write file larger than 100 bytes
            test_file.write_text("x" * 200)

            config = ExecutorConfig(max_file_size=100)
            ctx = ExecutorContext(config=config)
            tools = register_all(context=ctx)
            read_tool = next(t for t in tools if t.name == "read_file")

            result = read_tool(path=str(test_file))
            # Should be truncated
            assert "[Truncated:" in result


# ---------------------------------------------------------------------------
# Web tool context injection
# ---------------------------------------------------------------------------


class TestWebContextInjection:
    """Tests for fetch_url context injection."""

    def test_fetch_disabled_by_feature_flag(self):
        """fetch_url should return error when enable_fetch is False."""
        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext
        from tinycua.agent.tools import register_all

        config = ExecutorConfig(enable_fetch=False)
        ctx = ExecutorContext(config=config)
        tools = register_all(context=ctx)
        fetch_tool = next(t for t in tools if t.name == "fetch_url")

        result = fetch_tool(url="http://example.com")
        assert "error" in result or "disabled" in result

    def test_fetch_enabled_by_default(self):
        """fetch_url should work normally without context."""
        from tinycua.agent.tools.native.web import fetch_url

        # We can't test actual HTTP without a server, but the tool should be callable
        result = fetch_url(url="http://localhost:1/nonexistent", timeout=1)
        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# Python exec tool context injection
# ---------------------------------------------------------------------------


class TestPythonContextInjection:
    """Tests for run_python context injection."""

    def test_python_disabled_by_feature_flag(self):
        """run_python should return error when enable_python_exec is False."""
        from tinycua.agent.tools.context import ExecutorConfig, ExecutorContext
        from tinycua.agent.tools import register_all

        config = ExecutorConfig(enable_python_exec=False)
        ctx = ExecutorContext(config=config)
        tools = register_all(context=ctx)
        python_tool = next(t for t in tools if t.name == "run_python")

        result = python_tool(code="print('hello')")
        assert "error" in result or "disabled" in result

    def test_python_enabled_by_default(self):
        """run_python should work normally without context."""
        from tinycua.agent.tools.native.python_exec import run_python

        result = run_python(code="print('hello')")
        assert "hello" in result["stdout"]
        assert result["exit_code"] == 0
