"""Integration tests for run_python tool."""


def test_run_python_hello():
    """Execute simple print statement and capture stdout."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("print('hello world')")
    assert result["stdout"].strip() == "hello world"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert result["error"] is None


def test_run_python_syntax_error():
    """Return stderr with traceback for invalid Python code."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("print(undefined_var")
    assert result["exit_code"] != 0
    assert "error" in result["stderr"].lower() or "syntax" in result["stderr"].lower()


def test_run_python_timeout():
    """Infinite loop is terminated by timeout."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("while True: pass", timeout=1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_run_python_empty_code():
    """Empty code returns success with no output."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("")
    assert result["stdout"] == ""
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
