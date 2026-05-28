"""Tests for deprecation warnings on old import paths."""

import warnings

import pytest


class TestOldConfigDeprecation:
    """Tests for old Config class deprecation."""

    def test_old_config_class_emits_warning(self):
        """Verify importing/using old Config emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from tinycua_sdk.config import Config

            # Trigger the warning by instantiating
            Config()

            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_configure_function_emits_warning(self):
        """Verify calling configure() emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from tinycua_sdk.config import configure

            configure(backend_url="http://test.example.com")

            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_old_config_still_works(self):
        """Verify old Config class is still functional."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from tinycua_sdk.config import Config, configure

            # Test configure
            configure(
                backend_url="http://test.example.com",
                api_key="test-key",
                provider="openai",
                model="gpt-4",
                base_url="http://api.openai.com",
            )

            assert Config.BACKEND_URL == "http://test.example.com"
            assert Config.API_KEY == "test-key"
            assert Config.PROVIDER == "openai"
            assert Config.MODEL == "gpt-4"
            assert Config.BASE_URL == "http://api.openai.com"

            # Test from_env
            config_dict = Config.from_env()
            assert "provider" in config_dict
            assert "model" in config_dict
            assert "base_url" in config_dict
            assert "api_key" in config_dict
