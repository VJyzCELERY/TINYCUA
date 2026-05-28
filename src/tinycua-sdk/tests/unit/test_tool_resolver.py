"""Tests for tool resolver."""

from tinycua_sdk.tools.resolver import analyze_source, find_internal_calls


class TestToolResolver:
    """Test tool resolver."""

    def test_resolver_module_imports(self):
        """Test resolver module imports."""
        from tinycua_sdk.tools import resolver

        assert resolver is not None

    def test_analyze_source_function(self):
        """Test analyze_source function exists."""
        assert callable(analyze_source)

    def test_find_internal_calls_function(self):
        """Test find_internal_calls function exists."""
        assert callable(find_internal_calls)


class TestToolResolverFunctions:
    """Test tool resolver functions."""

    def test_analyze_source_with_code(self):
        """Test analyzing source code."""
        code = "import os\ndef test(): pass"
        deps = analyze_source(code)
        assert deps is not None
        assert isinstance(deps, list)

    def test_find_internal_calls_with_code(self):
        """Test finding internal calls."""
        code = "def foo(): bar()"
        calls = find_internal_calls(code)
        assert calls is not None
        assert isinstance(calls, set)
