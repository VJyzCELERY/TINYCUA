"""Unit tests for python_exec.py — mocking subprocess for timeout/errors."""


def test_run_python_runtime_error():
    """Runtime error in code returns stderr with traceback."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("raise ValueError('test error')")
    assert result["exit_code"] != 0
    assert "ValueError" in result["stderr"]
    assert "test error" in result["stderr"]


def test_run_python_import_success():
    """Code with import statement works."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("import math; print(math.pi)")
    assert result["exit_code"] == 0
    assert "3.14" in result["stdout"]


def test_run_python_multiline_code():
    """Multiline Python code executes correctly."""
    from tinycua.tools.native.python_exec import run_python

    code = """
x = 5
y = 10
print(f"x+y={x+y}")
"""
    result = run_python(code)
    assert result["exit_code"] == 0
    assert "x+y=15" in result["stdout"]


def test_run_python_unicode_output():
    """Unicode output is handled correctly."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("print('héllo wörld 🔥')")
    assert result["exit_code"] == 0
    assert "héllo wörld 🔥" in result["stdout"]


def test_run_python_very_large_output():
    """Large stdout output is handled."""
    from tinycua.tools.native.python_exec import run_python

    result = run_python("print('x' * 50000)")
    assert result["exit_code"] == 0
    assert len(result["stdout"]) >= 50000
