"""Tests for Pydantic-based immutable SDK config system."""

import os
import tempfile

import pytest
from pydantic import SecretStr

from tinycua_sdk.core.config import LLMConfig, SDKConfig


class TestDefaultConfig:
    """Test default configuration values."""

    def test_default_config_has_expected_values(self):
        """Verify defaults match current Config class."""
        config = SDKConfig()
        assert config.llm.provider == "openai-compatible"
        assert config.llm.model == "qwen/qwen3.5-9b"
        assert config.llm.base_url == "http://localhost:1234/v1"
        assert config.llm.temperature == 1.0
        assert config.memory.database_url == "sqlite:///./tinycua.db"
        assert config.memory.embedding_dimension == 1536
        assert config.session.max_turns == 100
        assert config.session.summary_enabled is True
        assert config.backend_url == "http://localhost:8000"
        assert config.environment == "dev"


class TestConfigImmutability:
    """Test that config objects are immutable."""

    def test_config_is_immutable(self):
        """Verify model_config = ConfigDict(frozen=True) works."""
        config = SDKConfig()
        with pytest.raises(Exception):  # pydantic raises ValidationError on frozen
            config.backend_url = "http://example.com"

    def test_config_model_copy_creates_modified(self):
        """Verify model_copy(update={...}) works."""
        config = SDKConfig()
        new_config = config.model_copy(update={"backend_url": "http://example.com"})
        assert new_config.backend_url == "http://example.com"
        assert config.backend_url == "http://localhost:8000"  # original unchanged


class TestConfigFromEnv:
    """Test loading config from environment variables."""

    def test_config_from_env_reads_env_vars(self, monkeypatch):
        """Set env vars, call from_env(), verify values."""
        monkeypatch.setenv("TINYCUA_ENV", "prod")
        monkeypatch.setenv("TINYCUA_BACKEND_URL", "http://prod.example.com")
        monkeypatch.setenv("TINYCUA_API_KEY", "secret-key-123")
        monkeypatch.setenv("TINYCUA_PROVIDER", "openai")
        monkeypatch.setenv("TINYCUA_MODEL", "gpt-4")
        monkeypatch.setenv("TINYCUA_BASE_URL", "http://api.openai.com")
        monkeypatch.setenv("TINYCUA_DATABASE_URL", "postgresql://localhost/tinycua")

        config = SDKConfig.from_env()
        assert config.environment == "prod"
        assert config.backend_url == "http://prod.example.com"
        assert config.llm.api_key.get_secret_value() == "secret-key-123"
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"
        assert config.llm.base_url == "http://api.openai.com"
        assert config.memory.database_url == "postgresql://localhost/tinycua"

    def test_config_from_env_with_partial_env_vars(self, monkeypatch):
        """Set only some TINYCUA_* env vars, verify unset fields use defaults."""
        monkeypatch.setenv("TINYCUA_MODEL", "gpt-4")
        # Only set model, leave everything else unset

        config = SDKConfig.from_env()
        assert config.llm.model == "gpt-4"
        # Unset fields should use defaults
        assert config.llm.provider == "openai-compatible"
        assert config.llm.base_url == "http://localhost:1234/v1"
        assert config.backend_url == "http://localhost:8000"
        assert config.environment == "dev"


class TestConfigFromYaml:
    """Test loading config from YAML files."""

    def test_config_from_yaml_loads_file(self):
        """Write temp YAML, load it, verify values."""
        yaml_content = """
llm:
  provider: openai
  model: gpt-4
  api_key: test-key-123
memory:
  database_url: postgresql://localhost/tinycua
session:
  max_turns: 50
backend_url: http://prod.example.com
environment: prod
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = SDKConfig.from_yaml(f.name)

        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"
        assert config.llm.api_key.get_secret_value() == "test-key-123"
        assert config.memory.database_url == "postgresql://localhost/tinycua"
        assert config.session.max_turns == 50
        assert config.backend_url == "http://prod.example.com"
        assert config.environment == "prod"

        os.unlink(f.name)

    def test_config_load_yaml_overrides_defaults(self):
        """YAML values override defaults."""
        yaml_content = """
llm:
  model: custom-model
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = SDKConfig.from_yaml(f.name)

        assert config.llm.model == "custom-model"
        # Other fields should still have defaults
        assert config.llm.provider == "openai-compatible"
        assert config.backend_url == "http://localhost:8000"

        os.unlink(f.name)

    def test_config_yaml_overrides_env(self, monkeypatch):
        """YAML values take precedence over env vars when both are present."""
        monkeypatch.setenv("TINYCUA_MODEL", "env-model")
        monkeypatch.setenv("TINYCUA_BACKEND_URL", "http://env.example.com")

        yaml_content = """
llm:
  model: yaml-model
backend_url: http://yaml.example.com
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = SDKConfig.load(f.name)

        # YAML should win over env
        assert config.llm.model == "yaml-model"
        assert config.backend_url == "http://yaml.example.com"

        os.unlink(f.name)

    def test_config_from_yaml_invalid_file_raises(self):
        """Verify error handling for bad YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(Exception):  # yaml.YAMLError
                SDKConfig.from_yaml(f.name)

        os.unlink(f.name)

    def test_config_from_yaml_missing_file_raises(self):
        """Verify error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            SDKConfig.from_yaml("/nonexistent/path/config.yaml")


class TestConfigSecretStr:
    """Test SecretStr handling for API keys."""

    def test_config_secret_str_for_api_key(self):
        """Verify api_key is SecretStr and .get_secret_value() works."""
        config = SDKConfig()
        assert isinstance(config.llm.api_key, SecretStr)
        assert config.llm.api_key.get_secret_value() == ""

        # Test with a real key
        config_with_key = SDKConfig(llm=LLMConfig(api_key=SecretStr("my-secret")))
        assert config_with_key.llm.api_key.get_secret_value() == "my-secret"


class TestConfigLoad:
    """Test the SDKConfig.load() method."""

    def test_config_load_with_no_path_returns_defaults(self):
        """Call SDKConfig.load(path=None), verify equivalent to SDKConfig()."""
        config = SDKConfig.load(path=None)
        default_config = SDKConfig()
        assert config.llm.provider == default_config.llm.provider
        assert config.llm.model == default_config.llm.model
        assert config.backend_url == default_config.backend_url
        assert config.environment == default_config.environment
