"""Tests for CORS configuration in main.py."""

import os
import sys

import pytest
from fastapi.middleware.cors import CORSMiddleware


class TestCORSSetup:
    """Tests that CORS is configured correctly at module level from env vars."""

    def test_cors_wildcard_with_credentials_raises(self, monkeypatch):
        """Module should raise ValueError when '*' is in origins with credentials."""
        monkeypatch.setenv("TINYCUA_CORS_ORIGINS", "*")
        # Remove cached module to force reimport
        if "tinycua_backend.main" in sys.modules:
            del sys.modules["tinycua_backend.main"]

        with pytest.raises(ValueError, match="Cannot use origins='\\*' with allow_credentials=True"):
            import tinycua_backend.main  # noqa: F401

    def test_cors_specific_origins_allowed(self, monkeypatch):
        """Module should succeed with specific origins and credentials."""
        monkeypatch.setenv("TINYCUA_CORS_ORIGINS", "https://example.com,https://app.example.com")
        if "tinycua_backend.main" in sys.modules:
            del sys.modules["tinycua_backend.main"]

        import tinycua_backend.main as main_module
        assert main_module._cors_origins == ["https://example.com", "https://app.example.com"]

    def test_cors_defaults_to_empty_list(self, monkeypatch):
        """Module should default to empty list when env var is not set."""
        monkeypatch.delenv("TINYCUA_CORS_ORIGINS", raising=False)
        if "tinycua_backend.main" in sys.modules:
            del sys.modules["tinycua_backend.main"]

        import tinycua_backend.main as main_module
        assert main_module._cors_origins == []

    def test_cors_middleware_registered(self, monkeypatch):
        """FastAPI app should have CORSMiddleware registered."""
        monkeypatch.delenv("TINYCUA_CORS_ORIGINS", raising=False)
        if "tinycua_backend.main" in sys.modules:
            del sys.modules["tinycua_backend.main"]

        import tinycua_backend.main as main_module
        middleware_classes = [m.cls for m in main_module.app.user_middleware]
        assert CORSMiddleware in middleware_classes
