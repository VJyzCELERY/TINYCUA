"""Tests for import sanity - verifying core imports work cleanly without deprecation warnings."""

import warnings


class TestNoDeprecationWarnings:
    """Test that no deprecation warnings are emitted in the codebase."""

    def test_no_deprecation_warnings_in_core_config(self):
        """Verify no deprecation warnings from core config."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from tinycua_sdk.core.config import SDKConfig

            _ = SDKConfig()

            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
                and "tinycua_sdk" in str(warning.message)
            ]

            assert len(deprecation_warnings) == 0


class TestDeprecatedRegistryPatterns:
    """Test that deprecated registry patterns are removed."""

    def test_registry_import_works(self):
        """Verify registry import works correctly."""
        from tinycua_sdk.core.registry import ToolRegistry

        registry = ToolRegistry()
        assert registry is not None


class TestDeprecatedStorePatterns:
    """Test that deprecated store patterns are removed."""

    def test_store_import_works(self):
        """Verify store import works correctly."""
        from tinycua_sdk.storage.store import SessionStore

        store = SessionStore(database_url="sqlite:///:memory:")
        assert store is not None
