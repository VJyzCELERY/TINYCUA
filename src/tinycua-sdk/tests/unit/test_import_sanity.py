"""Tests for import sanity - verifying core imports work cleanly without deprecation warnings."""

import warnings


class TestNoDeprecationWarnings:
    """Test that no deprecation warnings are emitted in the codebase."""

    def test_no_deprecation_warnings_on_import(self):
        """Verify no deprecation warnings when importing tinycua_sdk."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            import tinycua_sdk

            _ = tinycua_sdk

            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
                and "tinycua_sdk" in str(warning.message)
            ]

            assert len(deprecation_warnings) == 0


class TestCoreImports:
    """Test that core SDK imports work cleanly."""

    def test_agent_import_works(self):
        """Verify Agent import works correctly."""
        from tinycua_sdk import Agent

        assert Agent is not None

    def test_tool_import_works(self):
        """Verify tool decorator import works correctly."""
        from tinycua_sdk import tool

        assert tool is not None
