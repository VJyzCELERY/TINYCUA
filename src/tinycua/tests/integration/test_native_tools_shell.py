"""Integration tests for run_shell tool."""


def test_run_shell_echo():
    """Run a simple echo command and verify stdout, stderr, exit_code."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("echo hello")
    assert result["stdout"].strip() == "hello"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert result["error"] is None


def test_run_shell_invalid_command():
    """Verify error handling for a nonexistent command."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("nonexistent_command_xyz")
    assert result["exit_code"] != 0
    assert result["stderr"] != "" or result["error"] is not None


def test_run_shell_timeout():
    """Verify timeout kills a long-running process."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("sleep 60", timeout=1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1
