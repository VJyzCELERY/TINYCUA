"""Tests for deprecation - verifying old import paths raise ImportError."""

import sys
import warnings


class TestOldConfigDeprecation:
    """Tests for old Config class deprecation - now raises ImportError."""

    def test_old_config_import_raises_import_error(self):
        """Verify old Config import raises ImportError."""
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
                assert "deprecated" in str(e).lower()

    def test_old_configure_import_raises_import_error(self):
        """Verify old configure import raises ImportError."""
        # Clear any cached imports
        modules_to_clear = [k for k in sys.modules if k.startswith("tinycua_sdk")]
        for mod in modules_to_clear:
            del sys.modules[mod]

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            try:
                from tinycua_sdk.config import configure  # noqa: F401
                assert False, "Expected ImportError but none was raised"
            except ImportError as e:
                assert "deprecated" in str(e).lower()

    def test_new_config_works(self):
        """Verify new SDKConfig works correctly."""
        from tinycua_sdk.core.config import SDKConfig

        config = SDKConfig()
        assert config is not None
        assert config.backend_url == "http://localhost:8000"
