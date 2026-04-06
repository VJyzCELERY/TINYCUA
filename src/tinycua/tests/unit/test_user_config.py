"""Tests for UserConfig class."""

import os
from unittest.mock import patch



class TestUserConfigLoad:
    """Test UserConfig.load() with YAML > env > defaults merge."""

    def test_load_defaults_when_no_config_file(self, tmp_path):
        """Test loading returns defaults when no config file exists."""
        from tinycua.config.user_config import UserConfig

        non_existent = tmp_path / "nonexistent" / "config.yaml"
        config = UserConfig.load(path=non_existent)

        assert config.llm.provider == "lmstudio"
        assert config.llm.model == "qwen/qwen3.5-9b"
        assert config.backend_url == "http://localhost:8000"
        assert config.environment == "dev"

    def test_load_from_yaml_file(self, tmp_path):
        """Test loading config from a YAML file."""
        import yaml
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config_data = {
            "llm": {
                "provider": "ollama",
                "model": "llama3",
                "base_url": "http://localhost:11434",
            },
            "backend_url": "http://myserver:9000",
        }
        config_file.write_text(yaml.safe_dump(config_data))

        config = UserConfig.load(path=config_file)

        assert config.llm.provider == "ollama"
        assert config.llm.model == "llama3"
        assert config.llm.base_url == "http://localhost:11434"
        assert config.backend_url == "http://myserver:9000"

    def test_env_override_defaults(self):
        """Test environment variables override defaults."""
        from tinycua.config.user_config import UserConfig

        env = {
            "TINYCUA_PROVIDER": "openai",
            "TINYCUA_MODEL": "gpt-4",
            "TINYCUA_BACKEND_URL": "http://env-server:8000",
            "TINYCUA_ENV": "production",
        }

        with patch.dict(os.environ, env, clear=False):
            config = UserConfig.load()

        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"
        assert config.backend_url == "http://env-server:8000"
        assert config.environment == "production"

    def test_yaml_overrides_env(self, tmp_path):
        """Test YAML values override environment variables."""
        import yaml
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config_data = {
            "llm": {
                "provider": "ollama",
                "model": "llama3",
            },
        }
        config_file.write_text(yaml.safe_dump(config_data))

        env = {
            "TINYCUA_PROVIDER": "openai",
            "TINYCUA_MODEL": "gpt-4",
        }

        with patch.dict(os.environ, env, clear=False):
            config = UserConfig.load(path=config_file)

        # YAML should override env
        assert config.llm.provider == "ollama"
        assert config.llm.model == "llama3"

    def test_yaml_overrides_env_for_nested_fields(self, tmp_path):
        """Test YAML overrides only specified nested fields, keeping env for others."""
        import yaml
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config_data = {
            "llm": {
                "model": "llama3",
            },
        }
        config_file.write_text(yaml.safe_dump(config_data))

        env = {
            "TINYCUA_PROVIDER": "openai",
            "TINYCUA_BASE_URL": "http://env-api:1234",
        }

        with patch.dict(os.environ, env, clear=False):
            config = UserConfig.load(path=config_file)

        # YAML overrides model, env provides provider and base_url
        assert config.llm.model == "llama3"
        assert config.llm.provider == "openai"
        assert config.llm.base_url == "http://env-api:1234"

    def test_secretestr_handling(self, tmp_path):
        """Test API key is handled as SecretStr."""
        import yaml
        from pydantic import SecretStr
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config_data = {
            "llm": {
                "api_key": "my-secret-key",
            },
        }
        config_file.write_text(yaml.safe_dump(config_data))

        config = UserConfig.load(path=config_file)

        assert isinstance(config.llm.api_key, SecretStr)
        assert config.llm.api_key.get_secret_value() == "my-secret-key"


class TestUserConfigSave:
    """Test UserConfig.save() functionality."""

    def test_save_creates_config_file(self, tmp_path):
        """Test save creates a YAML config file."""
        from tinycua_sdk.core.config import SDKConfig
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config = SDKConfig()

        UserConfig.save(config, path=config_file)

        assert config_file.exists()

    def test_save_sets_0o600_permissions(self, tmp_path):
        """Test save sets file permissions to 0o600."""
        from tinycua_sdk.core.config import SDKConfig
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config = SDKConfig()

        UserConfig.save(config, path=config_file)

        # Check file permissions (owner read/write only)
        mode = config_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_save_creates_config_dir(self, tmp_path):
        """Test save creates parent directory if it doesn't exist."""
        from tinycua_sdk.core.config import SDKConfig
        from tinycua.config.user_config import UserConfig

        config_dir = tmp_path / ".tinycua"
        config_file = config_dir / "config.yaml"
        config = SDKConfig()

        assert not config_dir.exists()
        UserConfig.save(config, path=config_file)
        assert config_dir.exists()

    def test_save_writes_valid_yaml(self, tmp_path):
        """Test save writes valid YAML that can be reloaded."""
        import yaml
        from tinycua_sdk.core.config import SDKConfig
        from tinycua.config.user_config import UserConfig

        config_file = tmp_path / "config.yaml"
        config = SDKConfig()

        UserConfig.save(config, path=config_file)

        # Reload and verify
        with open(config_file) as f:
            data = yaml.safe_load(f)

        assert "llm" in data
        assert "memory" in data
        assert "session" in data
        assert "backend_url" in data


class TestUserConfigEnsureConfigDir:
    """Test UserConfig.ensure_config_dir() functionality."""

    def test_ensure_config_dir_creates_directory(self, tmp_path):
        """Test ensure_config_dir creates the directory."""
        from tinycua.config.user_config import UserConfig

        config_dir = tmp_path / ".tinycua"

        with patch.object(UserConfig, "DEFAULT_CONFIG_DIR", config_dir):
            result = UserConfig.ensure_config_dir()

        assert config_dir.exists()
        assert result == config_dir

    def test_ensure_config_dir_returns_existing_directory(self, tmp_path):
        """Test ensure_config_dir returns path if directory exists."""
        from tinycua.config.user_config import UserConfig

        config_dir = tmp_path / ".tinycua"
        config_dir.mkdir()

        with patch.object(UserConfig, "DEFAULT_CONFIG_DIR", config_dir):
            result = UserConfig.ensure_config_dir()

        assert result == config_dir


class TestUserConfigGenerateDefault:
    """Test UserConfig.generate_default_config() functionality."""

    def test_generate_default_config_creates_file(self, tmp_path):
        """Test generate_default_config creates a default config file."""
        from tinycua.config.user_config import UserConfig

        config_dir = tmp_path / ".tinycua"
        config_file = config_dir / "config.yaml"

        with patch.object(UserConfig, "DEFAULT_CONFIG_DIR", config_dir):
            with patch.object(UserConfig, "DEFAULT_CONFIG_FILE", config_file):
                config = UserConfig.generate_default_config()

        assert config_file.exists()
        assert config.llm.provider == "lmstudio"

    def test_generate_default_config_does_not_overwrite(self, tmp_path):
        """Test generate_default_config does not overwrite existing file."""
        import yaml
        from tinycua.config.user_config import UserConfig

        config_dir = tmp_path / ".tinycua"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(yaml.safe_dump({"llm": {"provider": "custom"}}))

        with patch.object(UserConfig, "DEFAULT_CONFIG_DIR", config_dir):
            with patch.object(UserConfig, "DEFAULT_CONFIG_FILE", config_file):
                config = UserConfig.generate_default_config()

        # Should load existing file, not overwrite
        assert config.llm.provider == "custom"
