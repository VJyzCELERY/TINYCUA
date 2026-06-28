"""Unit tests for Milestone 5 tool hardening (fetch_url, context.py)."""

from __future__ import annotations


import pytest

from tinycua.agent.tools.native.context import (
    WorkspaceNotBoundError,
    bind_workspace,
    resolve_workspace_path,
    to_workspace_relative,
)


class TestWorkspaceBindingHardened:
    """context.py raises when workspace unset (no cwd fallback)."""

    def test_unset_workspace_raises(self):
        """resolve_workspace_path raises WorkspaceNotBoundError when unset."""
        bind_workspace(None)
        with pytest.raises(WorkspaceNotBoundError):
            resolve_workspace_path("foo.txt")

    def test_set_workspace_resolves_relative(self, tmp_path):
        """Relative paths resolve under the workspace."""
        bind_workspace(tmp_path)
        resolved = resolve_workspace_path("backend/api.py")
        assert resolved == (tmp_path / "backend" / "api.py").resolve()

    def test_absolute_path_rerooted_under_workspace(self, tmp_path):
        """Absolute paths matching workspace subpaths are re-rooted."""
        bind_workspace(tmp_path)
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "api.py").write_text("x")
        # The model might pass /backend/api.py (stripped workspace prefix).
        # The tool re-roots it under the workspace.
        resolved = resolve_workspace_path("/backend/api.py")
        assert resolved == (tmp_path / "backend" / "api.py").resolve()

    def test_absolute_path_outside_workspace_raises(self, tmp_path):
        """Absolute paths outside the workspace raise ValueError."""
        bind_workspace(tmp_path)
        with pytest.raises(ValueError, match="outside workspace"):
            resolve_workspace_path("/etc/passwd")

    def test_to_workspace_relative(self, tmp_path):
        """to_workspace_relative converts absolute to relative."""
        bind_workspace(tmp_path)
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "api.py").write_text("x")
        rel = to_workspace_relative(str(tmp_path / "backend" / "api.py"))
        assert rel == "backend/api.py"

    def test_to_workspace_relative_not_under_workspace(self, tmp_path):
        """Paths outside the workspace are returned as-is."""
        bind_workspace(tmp_path)
        rel = to_workspace_relative("/etc/passwd")
        assert rel == "/etc/passwd"


class TestFetchUrlShape:
    """fetch_url returns a consistent dict shape (Milestone 5)."""

    def test_fetch_url_returns_dict_with_success_key(self):
        """Even on error, fetch_url returns a dict with 'success' key."""
        from tinycua.agent.tools.native.web import fetch_url

        result = fetch_url("http://localhost:1/nonexistent")
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is False
        assert "error" in result
        assert "url" in result

    def test_fetch_url_html_converted_to_markdown(self):
        """HTML responses are converted to markdown (no <title> tags)."""
        from tinycua.agent.tools.native.web import _process_response

        # Create a mock response.
        import httpx

        response = httpx.Response(
            200,
            text="<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>",
            headers={"content-type": "text/html"},
        )
        result = _process_response(response, 102400, "http://example.org/test")
        assert result["success"] is True
        assert "<title>" not in result["content"]
        assert "<h1>" not in result["content"]
        # html2text converts h1 to markdown header
        assert "Hello" in result["content"]

    def test_fetch_url_binary_content_refused(self):
        """Binary content-types are refused with a clear error."""
        from tinycua.agent.tools.native.web import _process_response

        import httpx

        response = httpx.Response(
            200,
            content=b"PNG_DATA",
            headers={"content-type": "image/png"},
        )
        result = _process_response(response, 102400, "http://example.org/img.png")
        assert result["success"] is False
        assert "binary" in result["error"].lower()
        assert result["content"] is None

    def test_fetch_url_http_error_returns_dict(self):
        """HTTP >=400 errors return a dict with success=False."""
        from tinycua.agent.tools.native.web import _process_response

        import httpx

        response = httpx.Response(404, headers={"content-type": "text/html"})
        result = _process_response(response, 102400, "http://example.org/404")
        assert result["success"] is False
        assert "404" in result["error"]
        assert result["content"] is None
