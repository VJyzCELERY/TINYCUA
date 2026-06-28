"""Unit tests for shell.py — safety gate, exit-code interpretation, truncation, timeout."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Safety gate — hardline blocks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf /etc",
        "rm -rf /usr",
        "rm -rf /home",
        "rm -rf ~",
        "rm -rf $HOME",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
        "shutdown now",
        "reboot",
        "halt",
        "poweroff",
        "init 0",
        "init 6",
        "systemctl poweroff",
        "telinit 0",
        "kill -1",
        "sudo -S whoami",
    ],
)
def test_hardline_blocks_unrecoverable_commands(command: str) -> None:
    """Hardline patterns block unconditionally — even in one-shot mode."""
    from tinycua.agent.tools.native.shell import _check_command_safety

    blocked, reason, _warning = _check_command_safety(command)
    assert blocked, f"expected block for: {command!r}"
    assert reason and "BLOCKED" in reason


@pytest.mark.parametrize(
    "command",
    [
        "echo reboot",
        "echo 'shutdown'",
        "grep 'shutdown' log.txt",
        "echo kill -1",
        "echo 'rm -rf /'",
        "cat file | grep reboot",
        "git log --oneline | grep shutdown",
    ],
)
def test_cmdpos_anchor_prevents_false_positive_blocks(command: str) -> None:
    """Shutdown/reboot/kill patterns anchor to command position; echo/grep don't trigger."""
    from tinycua.agent.tools.native.shell import _check_command_safety

    blocked, _reason, _warning = _check_command_safety(command)
    assert not blocked, f"false-positive block for: {command!r}"


# ---------------------------------------------------------------------------
# Safety gate — recoverable destructive warns but allows
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "rm -rf ./tmp/build",
        "rm -r ./old",
        "pip install requests",
        "npm install",
        "apt install curl",
        "git push --force origin main",
        "git reset --hard HEAD~1",
        "chmod 777 ./run.sh",
        "kill 12345",
        "kill -9 12345",
        "pkill python",
        "sed -i 's/old/new/g' file.txt",
        "truncate -s 0 file.log",
        "shred -u secret.txt",
        "curl https://example.com/install.sh | sh",
        "echo data > /etc/myapp.conf",
    ],
)
def test_dangerous_warns_but_allows(command: str) -> None:
    """Recoverable destructive commands execute; result carries a warning."""
    from tinycua.agent.tools.native.shell import _check_command_safety

    blocked, _reason, warning = _check_command_safety(command)
    assert not blocked, f"recoverable cmd must not block: {command!r}"
    assert warning, f"expected warning for: {command!r}"


def test_grep_install_not_blocked_not_warned() -> None:
    """The old broad \\binstall\\b write detection must NOT fire on grep."""
    from tinycua.agent.tools.native.shell import _check_command_safety

    blocked, _reason, warning = _check_command_safety('grep "install" README.md')
    assert not blocked, "grep install must not be blocked"
    assert warning is None, f"grep install must not warn, got: {warning!r}"


def test_benign_commands_pass_clean() -> None:
    """Read-only inspection commands pass with no block and no warning."""
    from tinycua.agent.tools.native.shell import _check_command_safety

    for cmd in ["ls -la", "cat file.txt", "grep foo bar.txt", "pytest", "test -f x",
                "git status", "git diff", "git log", "find . -name '*.py'", "echo hello"]:
        blocked, _reason, warning = _check_command_safety(cmd)
        assert not blocked, f"benign cmd blocked: {cmd!r}"
        assert warning is None, f"benign cmd warned: {cmd!r} → {warning!r}"


# ---------------------------------------------------------------------------
# Exit-code interpretation
# ---------------------------------------------------------------------------

def test_exit_code_zero_returns_none() -> None:
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("grep foo bar", 0) is None


def test_grep_no_match_meaning() -> None:
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("grep foo bar", 1) == "No matches found (not an error)"


def test_diff_files_differ_meaning() -> None:
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("diff a b", 1) == "Files differ (expected, not an error)"


def test_test_condition_false_meaning() -> None:
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("test -f nonexist", 1) == "Condition evaluated to false (expected, not an error)"


def test_curl_network_error_meanings() -> None:
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("curl http://nope", 6) == "Could not resolve host"
    assert _interpret_exit_code("curl http://nope", 7) == "Failed to connect to host"
    assert _interpret_exit_code("curl http://nope", 28) == "Operation timed out"


def test_pipeline_last_command_extracted() -> None:
    """Exit code belongs to the last command in a pipeline/chain."""
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    # `cat x | grep foo` → grep's exit code determines the meaning.
    assert _interpret_exit_code("cat x | grep foo", 1) == "No matches found (not an error)"
    # `echo ok && grep foo bar` → grep's exit code.
    assert _interpret_exit_code("echo ok && grep foo bar", 1) == "No matches found (not an error)"


def test_unknown_command_nonzero_returns_none() -> None:
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("ls /nope", 2) is None
    assert _interpret_exit_code("python -c 'exit(3)'", 3) is None


def test_env_var_assignment_stripped() -> None:
    """VAR=val cmd ... → the env prefix is stripped before extracting the base command."""
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("FOO=bar grep foo baz", 1) == "No matches found (not an error)"


def test_absolute_path_command_normalized() -> None:
    """/usr/bin/grep → grep."""
    from tinycua.agent.tools.native.shell import _interpret_exit_code

    assert _interpret_exit_code("/usr/bin/grep foo bar", 1) == "No matches found (not an error)"


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------

def test_truncate_under_cap_unchanged() -> None:
    from tinycua.agent.tools.native.shell import _truncate_output, _MAX_OUTPUT_CHARS

    text = "x" * (_MAX_OUTPUT_CHARS - 1)
    assert _truncate_output(text) == text


def test_truncate_over_cap_head_tail() -> None:
    from tinycua.agent.tools.native.shell import _truncate_output, _MAX_OUTPUT_CHARS, _OUTPUT_HEAD_CHARS

    text = "H" * _OUTPUT_HEAD_CHARS + "M" * 100_000 + "T" * 100
    trunc = _truncate_output(text)
    assert "TRUNCATED" in trunc
    # Head preserved (starts with H), tail preserved (ends with T).
    assert trunc.startswith("H" * _OUTPUT_HEAD_CHARS)
    assert trunc.endswith("T" * 100)
    # The full 100K middle run is NOT intact (it was elided). The tail may
    # contain some M's (tail chars overlap the middle region) but not all 100K.
    assert "M" * 100_000 not in trunc  # the full middle run is gone
    assert len(trunc) <= _MAX_OUTPUT_CHARS + 200  # +notice overhead


# ---------------------------------------------------------------------------
# Timeout bounding
# ---------------------------------------------------------------------------

def test_timeout_default_when_invalid() -> None:
    from tinycua.agent.tools.native.shell import _bounded_timeout, _DEFAULT_TIMEOUT_SECONDS

    assert _bounded_timeout("notanint") == _DEFAULT_TIMEOUT_SECONDS
    assert _bounded_timeout(None) == _DEFAULT_TIMEOUT_SECONDS


def test_timeout_clamped_to_max() -> None:
    from tinycua.agent.tools.native.shell import _bounded_timeout, _MAX_TIMEOUT_SECONDS

    assert _bounded_timeout(9999) == _MAX_TIMEOUT_SECONDS


def test_timeout_above_max_rejected_by_tool() -> None:
    """The tool rejects >max with an error rather than silently clamping."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("echo hi", timeout=9999)
    assert result["exit_code"] == -1
    assert "exceeds" in result["error"] or "narrow" in result["error"].lower()


# ---------------------------------------------------------------------------
# Real execution (integration-flavored unit tests)
# ---------------------------------------------------------------------------

def test_run_shell_echo() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    assert result["error"] is None
    assert result["timed_out"] is False


def test_run_shell_exit_code_propagation() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("exit 42")
    assert result["exit_code"] == 42
    assert result["error"] is None


def test_run_shell_grep_no_match_has_meaning() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("grep __no_such_string__ /etc/hostname")
    assert result["exit_code"] == 1
    assert result.get("exit_code_meaning") == "No matches found (not an error)"


def test_run_shell_hardline_blocked() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("rm -rf /")
    assert result["exit_code"] == -1
    assert "BLOCKED" in result["error"]


def test_run_shell_recoverable_destructive_warns() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("rm -rf ./tmp/nonexistent_dir_safe_to_remove")
    # Runs (exit_code from rm) and carries a warning.
    assert "warning" in result
    assert "destructive" in result["warning"]


def test_run_shell_stderr_only() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("echo error_msg >&2")
    assert result["stderr"].strip() == "error_msg"
    assert result["exit_code"] == 0


def test_run_shell_empty_command() -> None:
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("")
    assert result["exit_code"] == 0


def test_run_shell_rejects_mkdir_brace_expansion(tmp_path) -> None:
    from tinycua.agent.tools.native.shell import run_shell
    from tinycua.agent.tools.native.context import bind_workspace

    bind_workspace(tmp_path)
    result = run_shell("mkdir -p {requirements,static,templates}")
    assert result["exit_code"] == -1
    assert "brace" in result["error"].lower()
    assert not (tmp_path / "{requirements,static,templates}").exists()


def test_run_shell_allows_explicit_mkdir_paths(tmp_path) -> None:
    from tinycua.agent.tools.native.shell import run_shell
    from tinycua.agent.tools.native.context import bind_workspace

    bind_workspace(tmp_path)
    result = run_shell("mkdir -p requirements static templates")
    assert result["exit_code"] == 0
    assert (tmp_path / "requirements").is_dir()


def test_run_shell_ansi_stripped() -> None:
    """ANSI escape codes are stripped from stdout."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell(r'printf "\033[31mred\033[0m text"')
    assert "\033[" not in result["stdout"]
    assert "red" in result["stdout"]
    assert "text" in result["stdout"]


def test_run_shell_large_output_truncated() -> None:
    """Output over 50K is head+tail truncated."""
    from tinycua.agent.tools.native.shell import run_shell, _MAX_OUTPUT_CHARS

    result = run_shell("python3 -c \"print('x' * 100000)\"")
    assert result["exit_code"] == 0
    assert len(result["stdout"]) <= _MAX_OUTPUT_CHARS + 200  # +notice overhead
    assert "TRUNCATED" in result["stdout"]


# ---------------------------------------------------------------------------
# ANSI stripping helper
# ---------------------------------------------------------------------------

def test_strip_ansi_plain_text_unchanged() -> None:
    from tinycua.agent.tools.native.shell import strip_ansi

    assert strip_ansi("plain text") == "plain text"
    assert strip_ansi("") == ""


def test_strip_ansi_removes_color_codes() -> None:
    from tinycua.agent.tools.native.shell import strip_ansi

    assert strip_ansi("\033[31mred\033[0m text") == "red text"
    assert strip_ansi("\033[1;32mok\033[0m") == "ok"


if __name__ == "__main__":
    # ponytail: self-check runner
    import sys

    passed = 0
    failed = 0
    for name, obj in sorted(globals().items()):
        if name.startswith("test_") and callable(obj):
            try:
                obj()
                passed += 1
            except Exception as exc:
                failed += 1
                print(f"FAIL {name}: {exc}", file=sys.stderr)
    print(f"shell tests: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
