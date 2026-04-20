"""Tests for setup wizard - first startup detection, config flow, validation."""

import pytest
from unittest.mock import patch


class TestFirstStartupDetection:
    """Test first startup detection."""

    def test_detects_first_startup(self, tmp_path):
        """Test detects first startup."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        with patch("tinycua.config.user_config.CONFIG_DIR", tmp_path):
            wizard = SetupWizard()
            assert wizard.is_first_startup() is True

    def test_detects_existing_installation(self, tmp_path):
        """Test detects existing installation."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text('{"model": "test"}')

        with patch("tinycua.config.user_config.CONFIG_DIR", tmp_path):
            wizard = SetupWizard()
            assert wizard.is_first_startup() is False

    def test_config_file_presence_check(self, tmp_path):
        """Test config file presence check."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        with patch("tinycua.config.user_config.CONFIG_DIR", tmp_path):
            wizard = SetupWizard()
            assert wizard.config_exists() is False


class TestConfigurationFlow:
    """Test configuration flow."""

    def test_welcome_message_display(self):
        """Test welcome message displays."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        wizard = SetupWizard()
        message = wizard.get_welcome_message()
        assert "welcome" in message.lower()

    def test_mode_selection_flow(self):
        """Test mode selection flow."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        wizard = SetupWizard()
        modes = wizard.get_available_modes()
        assert "local" in modes
        assert "deployed" in modes

    def test_account_creation_flow(self):
        """Test account creation flow."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        wizard = SetupWizard()
        result = wizard.create_account(username="testuser", password="testpass")
        assert result.success is True


class TestValidation:
    """Test input validation."""

    def test_username_validation(self):
        """Test username validation."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        wizard = SetupWizard()
        assert wizard.validate_username("validuser") is True
        assert wizard.validate_username("ab") is False
        assert wizard.validate_username("") is False

    def test_password_validation(self):
        """Test password validation."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        wizard = SetupWizard()
        assert wizard.validate_password("securepass123") is True
        assert wizard.validate_password("short") is False
        assert wizard.validate_password("") is False

    def test_url_validation(self):
        """Test URL validation."""
        try:
            from tinycua.config.setup_wizard import SetupWizard
        except ImportError:
            pytest.skip("SetupWizard not yet implemented")

        wizard = SetupWizard()
        assert wizard.validate_url("http://localhost:1234") is True
        assert wizard.validate_url("https://api.example.com") is True
        assert wizard.validate_url("invalid") is False
        assert wizard.validate_url("") is False
