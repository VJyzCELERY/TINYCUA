"""Tests for CLI REPL module."""

import pytest


class TestCLIRepl:
    """Test CLI REPL module."""

    def test_repl_module_imports(self):
        """Verify REPL module can be imported."""
        # Just check that the module exists (may fail if rich not installed)
        try:
            from tinycua_sdk.cli import repl
            assert repl is not None
        except ModuleNotFoundError:
            pytest.skip("rich module not installed")
