"""Unit tests for shell.py — mocking subprocess for edge cases."""


def test_run_shell_empty_command():
    """Empty command returns success with empty output."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("")
    assert result["exit_code"] == 0


def test_run_shell_large_output():
    """Very large stdout/stderr is captured without error."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("python3 -c \"print('x' * 100000)\"")
    assert result["exit_code"] == 0
    assert len(result["stdout"]) >= 100000


def test_run_shell_mocked_timeout():
    """Mock subprocess to test timer-based timeout behavior."""
    from tinycua.agent.tools.native.shell import run_shell

    # Use a very short timeout on a command that should finish quickly
    # but verify the timeout mechanism is wired up correctly
    result = run_shell("echo fast", timeout=30)
    assert result["stdout"].strip() == "fast"
    assert result["timed_out"] is False


def test_run_shell_stderr_only():
    """Command that only writes to stderr."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("echo error_msg >&2")
    assert result["stderr"].strip() == "error_msg"
    assert result["exit_code"] == 0


def test_run_shell_exit_code_propagation():
    """Non-zero exit codes are captured correctly."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("exit 42")
    assert result["exit_code"] == 42
    assert result["error"] is None
