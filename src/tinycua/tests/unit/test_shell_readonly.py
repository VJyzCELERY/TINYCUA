"""Unit tests for run_shell_readonly tool."""

import pytest


def test_readonly_allows_ls():
    """ls is a read-only command and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("ls")
    assert result["exit_code"] == 0
    assert result["error"] is None


def test_readonly_allows_cat():
    """cat without redirection is read-only and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("cat /dev/null")
    assert result["exit_code"] == 0
    assert result["error"] is None


def test_readonly_allows_echo():
    """echo without redirection is read-only and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


def test_readonly_blocks_rm():
    """rm should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("rm -rf /tmp/test")
    assert result["exit_code"] == -1
    assert "rm" in result["error"]


def test_readonly_blocks_mv():
    """mv should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("mv a b")
    assert result["exit_code"] == -1
    assert "mv" in result["error"]


def test_readonly_blocks_cp():
    """cp should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("cp a b")
    assert result["exit_code"] == -1
    assert "cp" in result["error"]


def test_readonly_blocks_mkdir():
    """mkdir should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("mkdir /tmp/test_dir")
    assert result["exit_code"] == -1
    assert "mkdir" in result["error"]


def test_readonly_blocks_redirection_write():
    """Output redirection (> file) should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("echo hello > /tmp/test.txt")
    assert result["exit_code"] == -1
    assert ">" in result["error"]


def test_readonly_blocks_redirection_append():
    """Append redirection (>> file) should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("echo hello >> /tmp/test.txt")
    assert result["exit_code"] == -1
    assert ">>" in result["error"]


def test_readonly_blocks_sed_inplace():
    """sed -i should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("sed -i 's/old/new/g' file.txt")
    assert result["exit_code"] == -1
    assert "sed" in result["error"]


def test_readonly_blocks_tee():
    """tee should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("echo hello | tee /tmp/test.txt")
    assert result["exit_code"] == -1
    assert "tee" in result["error"]


def test_readonly_blocks_pip_install():
    """pip install should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("pip install requests")
    assert result["exit_code"] == -1
    assert "pip" in result["error"]


def test_readonly_blocks_touch():
    """touch should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("touch /tmp/test.txt")
    assert result["exit_code"] == -1
    assert "touch" in result["error"]


def test_readonly_allows_git_status():
    """git status is read-only and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("git status")
    # git status may fail if not in a repo, but it should not be blocked
    assert "git mutation" not in str(result.get("error", ""))


def test_readonly_allows_git_diff():
    """git diff is read-only and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("git diff")
    assert "git mutation" not in str(result.get("error", ""))


def test_readonly_allows_pytest():
    """pytest is read-only (runs tests) and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("pytest --version")
    assert result["exit_code"] == 0
    assert result["error"] is None


def test_readonly_allows_python_c():
    """python -c is read-only for inspection and should be allowed."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("python -c \"print('hello')\"")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


def test_readonly_blocks_git_commit():
    """git commit should be blocked."""
    from tinycua.agent.tools.native.shell_readonly import run_shell_readonly

    result = run_shell_readonly("git commit -m 'test'")
    assert result["exit_code"] == -1
    assert "git mutation" in result["error"]


def test_detect_write_intent_helper():
    """Test the detection helper directly."""
    from tinycua.agent.tools.native.shell_readonly import _detect_write_intent

    assert _detect_write_intent("rm -rf /") is not None
    assert _detect_write_intent("ls -la") is None
    assert _detect_write_intent("cat file.txt") is None
    assert _detect_write_intent("echo hello > file.txt") is not None
    assert _detect_write_intent("pip install foo") is not None
    assert _detect_write_intent("git status") is None
    assert _detect_write_intent("git diff") is None