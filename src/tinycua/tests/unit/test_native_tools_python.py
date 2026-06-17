"""Unit tests for python_exec.py — mocking subprocess for timeout/errors."""


def test_run_python_caps_model_requested_timeout(monkeypatch):
    """Excessive model-supplied timeout values are capped for responsiveness."""
    from tinycua.agent.tools.native import python_exec

    observed = {}

    class Completed:
        stdout = "ok"
        stderr = ""
        returncode = 0

    def fake_run(*args, **kwargs):
        observed["timeout"] = kwargs.get("timeout")
        return Completed()

    monkeypatch.setattr(python_exec.subprocess, "run", fake_run)

    result = python_exec.run_python("print('ok')", timeout=1_200_000)

    assert observed["timeout"] == 30
    assert result["stdout"] == "ok"


def test_run_python_runtime_error():
    """Runtime error in code returns stderr with traceback."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("raise ValueError('test error')")
    assert result["exit_code"] != 0
    assert "ValueError" in result["stderr"]
    assert "test error" in result["stderr"]


def test_run_python_import_success():
    """Code with import statement works."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("import math; print(math.pi)")
    assert result["exit_code"] == 0
    assert "3.14" in result["stdout"]


def test_run_python_multiline_code():
    """Multiline Python code executes correctly."""
    from tinycua.agent.tools.native.python_exec import run_python

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
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("print('héllo wörld 🔥')")
    assert result["exit_code"] == 0
    assert "héllo wörld 🔥" in result["stdout"]


def test_run_python_very_large_output():
    """Large stdout output is handled."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("print('x' * 50000)")
    assert result["exit_code"] == 0
    assert len(result["stdout"]) >= 50000
