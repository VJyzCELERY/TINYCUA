"""Tests for context tools."""

import warnings


class TestContextTools:
    """Test context tools."""

    def test_context_tools_module_imports(self):
        """Test context tools module imports."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from tinycua_sdk.tools import context_tools

            assert context_tools is not None

    def test_context_tools_class_import(self):
        """Test context tools class can be imported."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from tinycua_sdk.tools.context_tools import ContextTools

            assert ContextTools is not None

    def test_context_tools_init(self):
        """Test context tools initialization."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from tinycua_sdk.tools.context_tools import ContextTools

            tools = ContextTools()
            assert tools is not None
