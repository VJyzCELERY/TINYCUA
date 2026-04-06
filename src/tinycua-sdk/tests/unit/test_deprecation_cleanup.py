"""Tests for deprecation cleanup - verifying old import paths raise ImportError."""

import sys
import warnings


class TestDeprecatedConfigImport:
    """Test that old config import paths raise ImportError with helpful message."""

    def test_old_config_import_raises_import_error(self):
        """Verify old import path raises ImportError with helpful message."""
        # Clear any cached imports
        modules_to_clear = [k for k in sys.modules if k.startswith("tinycua_sdk")]
        for mod in modules_to_clear:
            del sys.modules[mod]

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            # Try to import the module and access Config - should raise ImportError
            try:
                import tinycua_sdk.config
                _ = tinycua_sdk.config.Config
                assert False, "Expected ImportError but none was raised"
            except ImportError as e:
                # Verify helpful message is present
                assert "tinycua_sdk.config is deprecated" in str(e)
                assert "tinycua_sdk.core.config" in str(e)

    def test_old_config_from_import_raises_import_error(self):
        """Verify 'from tinycua_sdk.config import Config' raises ImportError."""
        # Clear any cached imports
        modules_to_clear = [k for k in sys.modules if k.startswith("tinycua_sdk")]
        for mod in modules_to_clear:
            del sys.modules[mod]

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            try:
                from tinycua_sdk.config import Config  # noqa: F401
                assert False, "Expected ImportError but none was raised"
            except ImportError as e:
                # Verify helpful message is present
                assert "tinycua_sdk.config is deprecated" in str(e)
                assert "tinycua_sdk.core.config" in str(e)

    def test_new_config_import_works(self):
        """Verify new import path works correctly."""
        from tinycua_sdk.core.config import SDKConfig

        config = SDKConfig()
        assert config is not None
        assert config.backend_url == "http://localhost:8000"


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
