"""Tests for the wizard module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests


class TestIsFirstStartup:
    """Tests for is_first_startup function."""

    def test_first_startup_no_config(self, tmp_path):
        """Test returns True when no config exists."""
        with patch("tinycua.config.user_config.UserConfig") as mock_config_class:
            mock_config_class.DEFAULT_CONFIG_DIR = tmp_path
            from tinycua.config.wizard import is_first_startup

            result = is_first_startup(str(tmp_path))
            assert result is True

    def test_not_first_startup_config_exists(self, tmp_path):
        """Test returns False when config exists."""
        config_dir = tmp_path / ".tinycua"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("llm:\n  provider: lmstudio\n")

        from tinycua.config.wizard import is_first_startup

        result = is_first_startup(str(config_dir))
        assert result is False


class TestWizardFlow:
    """Tests for SetupWizard class."""

    def test_wizard_initialization(self, tmp_path):
        """Test wizard can be initialized."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        assert wizard.config_dir == tmp_path

    def test_wizard_storage_mode_local(self, tmp_path):
        """Test setting storage mode to local."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_storage_mode("local")
        assert wizard.storage_mode == "local"

    def test_wizard_storage_mode_remote(self, tmp_path):
        """Test setting storage mode to remote."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_storage_mode("remote")
        assert wizard.storage_mode == "remote"

    def test_wizard_invalid_storage_mode(self, tmp_path):
        """Test invalid storage mode raises error."""
        from tinycua.config.wizard import SetupWizard, WizardError

        wizard = SetupWizard(config_dir=tmp_path)
        with pytest.raises(WizardError):
            wizard.set_storage_mode("invalid")

    def test_wizard_set_account(self, tmp_path):
        """Test setting account credentials."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_account("testuser", "test@example.com", "Password123!")
        assert wizard.username == "testuser"
        assert wizard.email == "test@example.com"

    def test_wizard_set_llm_config(self, tmp_path):
        """Test setting LLM configuration."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_llm_config(
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="",
        )
        assert wizard.llm_provider == "lmstudio"
        assert wizard.llm_model == "qwen/qwen3.5-9b"

    def test_wizard_validation_empty_username(self, tmp_path):
        """Test validation fails for empty username."""
        from tinycua.config.wizard import SetupWizard, WizardValidationError

        wizard = SetupWizard(config_dir=tmp_path)
        with pytest.raises(WizardValidationError):
            wizard.validate_account("", "test@example.com", "Password123!")

    def test_wizard_validation_invalid_email(self, tmp_path):
        """Test validation fails for invalid email."""
        from tinycua.config.wizard import SetupWizard, WizardValidationError

        wizard = SetupWizard(config_dir=tmp_path)
        with pytest.raises(WizardValidationError):
            wizard.validate_account("testuser", "invalid-email", "Password123!")

    def test_wizard_validation_password_mismatch(self, tmp_path):
        """Test validation fails for password mismatch."""
        from tinycua.config.wizard import SetupWizard, WizardValidationError

        wizard = SetupWizard(config_dir=tmp_path)
        with pytest.raises(WizardValidationError):
            wizard.validate_account(
                "testuser", "test@example.com", "Password123!", "password456"
            )

    def test_wizard_validation_short_password(self, tmp_path):
        """Test validation fails for short password."""
        from tinycua.config.wizard import SetupWizard, WizardValidationError

        wizard = SetupWizard(config_dir=tmp_path)
        with pytest.raises(WizardValidationError):
            wizard.validate_account("testuser", "test@example.com", "short")


class TestWizardCompletion:
    """Tests for wizard completion and config saving."""

    def test_wizard_complete_local_mode(self, tmp_path):
        """Test wizard completes successfully in local mode."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_storage_mode("local")
        wizard.set_account("testuser", "test@example.com", "Password123!")
        wizard.set_llm_config(
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
        )

        config = wizard.complete()
        assert config is not None
        assert config.llm.provider == "lmstudio"
        assert config.llm.model == "qwen/qwen3.5-9b"

    def test_wizard_complete_remote_mode(self, tmp_path):
        """Test wizard completes successfully in remote mode."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_storage_mode("remote")
        wizard.set_account("testuser", "test@example.com", "Password123!")
        wizard.set_llm_config(
            provider="openai",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
            api_key="test-key",
        )

        config = wizard.complete()
        assert config is not None
        assert config.llm.provider == "openai"
        assert config.memory.database_url != f"sqlite:///{tmp_path}/data.db"

    def test_wizard_complete_saves_config(self, tmp_path):
        """Test wizard saves config to file."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_storage_mode("local")
        wizard.set_account("testuser", "test@example.com", "Password123!")
        wizard.set_llm_config(
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
        )

        config = wizard.complete()
        config_file = tmp_path / "config.yaml"
        assert config_file.exists()

    def test_wizard_complete_creates_db_file(self, tmp_path):
        """Test wizard creates database file in local mode."""
        from tinycua.config.wizard import SetupWizard

        wizard = SetupWizard(config_dir=tmp_path)
        wizard.set_storage_mode("local")
        wizard.set_account("testuser", "test@example.com", "Password123!")
        wizard.set_llm_config(
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
        )

        wizard.complete()
        db_file = tmp_path / "data.db"
        assert db_file.exists()


class TestInteractiveFunctions:
    """Tests for interactive prompt functions."""

    @patch("builtins.input")
    def test_show_welcome(self, mock_input):
        """Test show_welcome prints welcome message."""
        from tinycua.config.wizard import show_welcome
        show_welcome()

    @patch("builtins.input")
    def test_prompt_storage_mode_local(self, mock_input):
        """Test prompt_storage_mode returns local."""
        from tinycua.config.wizard import prompt_storage_mode
        mock_input.return_value = "1"
        result = prompt_storage_mode()
        assert result == "local"

    @patch("builtins.input")
    def test_prompt_storage_mode_remote(self, mock_input):
        """Test prompt_storage_mode returns remote."""
        from tinycua.config.wizard import prompt_storage_mode
        mock_input.return_value = "2"
        result = prompt_storage_mode()
        assert result == "remote"

    @patch("builtins.input")
    def test_prompt_storage_mode_invalid_then_valid(self, mock_input):
        """Test prompt_storage_mode with invalid then valid input."""
        from tinycua.config.wizard import prompt_storage_mode
        mock_input.side_effect = ["3", "1"]
        result = prompt_storage_mode()
        assert result == "local"

    @patch("builtins.input")
    def test_prompt_account_creation(self, mock_input):
        """Test prompt_account_creation returns account dict."""
        from tinycua.config.wizard import prompt_account_creation
        mock_input.side_effect = ["testuser", "test@example.com", "Password123!", "Password123!"]
        result = prompt_account_creation()
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"

    @patch("builtins.input")
    def test_prompt_llm_configuration(self, mock_input):
        """Test prompt_llm_configuration returns config dict."""
        from tinycua.config.wizard import prompt_llm_configuration
        mock_input.side_effect = ["", "", "", ""]
        result = prompt_llm_configuration()
        assert result["provider"] == "lmstudio"
        assert result["model"] == "qwen/qwen3.5-9b"

    @patch("builtins.input")
    def test_prompt_llm_configuration_custom(self, mock_input):
        """Test prompt_llm_configuration with custom values."""
        from tinycua.config.wizard import prompt_llm_configuration
        mock_input.side_effect = ["openai", "gpt-4", "https://api.openai.com/v1", "sk-test"]
        result = prompt_llm_configuration()
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"
        assert result["api_key"] == "sk-test"


class TestHelperFunctions:
    """Tests for helper functions."""

    @patch("requests.get")
    def test_is_lmstudio_available_true(self, mock_get):
        """Test is_lmstudio_available returns True when available."""
        from tinycua.config.wizard import is_lmstudio_available
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        assert is_lmstudio_available() is True

    @patch("requests.get")
    def test_is_lmstudio_available_false(self, mock_get):
        """Test is_lmstudio_available returns False when not available."""
        from tinycua.config.wizard import is_lmstudio_available
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        assert is_lmstudio_available() is False

    @patch("requests.get")
    def test_test_connection_success(self, mock_get):
        """Test test_connection returns True on success."""
        from tinycua.config.wizard import test_connection
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        assert test_connection("http://localhost:8000") is True

    @patch("requests.get")
    def test_test_connection_404(self, mock_get):
        """Test test_connection returns True on 404 (server running)."""
        from tinycua.config.wizard import test_connection
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        assert test_connection("http://localhost:8000") is True

    @patch("requests.get")
    def test_test_connection_failure(self, mock_get):
        """Test test_connection returns False on failure."""
        from tinycua.config.wizard import test_connection
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        assert test_connection("http://localhost:8000") is False
