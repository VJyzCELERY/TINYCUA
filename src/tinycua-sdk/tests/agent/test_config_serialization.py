"""Unit tests for AgentConfig JSON/YAML serialization."""

import json
import os
import tempfile

import pytest
import yaml
from pathlib import Path

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy


class TestFromJson:
    """Tests for AgentConfig.from_json() method."""

    def test_from_json_parses_json_string(self):
        """Test parsing valid JSON string."""
        json_str = json.dumps({"name": "test-agent", "model": "gpt-5-nano"})
        config = AgentConfig.from_json(json_str)
        assert config.name == "test-agent"
        assert config.model == "gpt-5-nano"

    def test_from_json_loads_from_path_object(self):
        """Test loading from Path object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "test-agent", "model": "gpt-5-nano"}, f)
            temp_path = Path(f.name)

        try:
            config = AgentConfig.from_json(temp_path)
            assert config.name == "test-agent"
            assert config.model == "gpt-5-nano"
        finally:
            temp_path.unlink()

    def test_from_json_loads_from_str_path(self):
        """Test loading from string file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "test-agent", "model": "gpt-5-nano"}, f)
            temp_path = f.name

        try:
            config = AgentConfig.from_json(temp_path)
            assert config.name == "test-agent"
            assert config.model == "gpt-5-nano"
        finally:
            Path(temp_path).unlink()

    def test_from_json_accepts_dict_directly(self):
        """Test that dict input is used directly."""
        data = {"name": "test-agent", "model": "gpt-5-nano"}
        config = AgentConfig.from_json(data)
        assert config.name == "test-agent"
        assert config.model == "gpt-5-nano"

    def test_from_json_handles_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            AgentConfig.from_json("not valid json {")

    def test_from_json_handles_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Empty JSON input"):
            AgentConfig.from_json("")

    def test_from_json_handles_missing_file(self):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            AgentConfig.from_json(Path("nonexistent/file.json"))

    def test_from_json_parses_all_fields(self):
        """Test parsing all configuration fields."""
        json_str = json.dumps({
            "name": "my-agent",
            "instructions": "Be helpful.",
            "system_prompt": "You are a helpful assistant.",
            "model": "gpt-5-nano",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test123",
            "tools": ["tool1", "tool2"],
            "policy": {"max_tool_calls": 5, "parallel_tool_calls": False, "temperature": 0.5},
            "skills": ["web-researcher"],
            "skill_dirs": ["/tmp/skills"],
            "auto_load_dependencies": False,
            "metadata": {"key": "value"}
        })
        config = AgentConfig.from_json(json_str)
        assert config.name == "my-agent"
        assert config.instructions == "Be helpful."
        assert config.system_prompt == "You are a helpful assistant."
        assert config.model == "gpt-5-nano"
        assert config.provider == "openai"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.api_key == "sk-test123"
        assert config.tools == ["tool1", "tool2"]
        assert config.policy.max_tool_calls == 5
        assert config.policy.parallel_tool_calls is False
        assert config.policy.temperature == 0.5
        assert config.skills == ["web-researcher"]
        assert config.skill_dirs == [Path("/tmp/skills")]
        assert config.auto_load_dependencies is False
        assert config.metadata == {"key": "value"}

    def test_from_json_partial_config_uses_defaults(self):
        """Test that partial config uses default values."""
        json_str = '{"name": "test-agent"}'
        config = AgentConfig.from_json(json_str)
        assert config.name == "test-agent"
        assert config.model == "gpt-5-nano"  # Should match dataclass default
        assert config.provider == "openai"
        assert config.instructions == ""

    def test_from_json_empty_object_uses_defaults(self):
        """Test that empty JSON object uses default values."""
        json_str = "{}"
        config = AgentConfig.from_json(json_str)
        assert config.name == "assistant"  # Default name
        assert config.model == "gpt-5-nano"  # Default model

    def test_from_json_unknown_fields_ignored(self):
        """Test that unknown fields are ignored."""
        json_str = '{"name": "test-agent", "unknown_field": "value", "another": 123}'
        config = AgentConfig.from_json(json_str)
        assert config.name == "test-agent"

    def test_from_json_null_optional_fields(self):
        """Test that null values for optional fields are handled."""
        json_str = '{"name": "test-agent", "api_key": null, "base_url": null}'
        config = AgentConfig.from_json(json_str)
        assert config.api_key is None
        assert config.base_url is None


class TestToJson:
    """Tests for AgentConfig.to_json() method."""

    def test_to_json_returns_valid_json(self):
        """Test that to_json returns valid JSON string."""
        config = AgentConfig(name="test-agent", model="gpt-5-nano")
        json_str = config.to_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "test-agent"
        assert parsed["model"] == "gpt-5-nano"

    def test_to_json_includes_all_fields(self):
        """Test that to_json includes all configuration fields."""
        config = AgentConfig(
            name="my-agent",
            instructions="Be helpful.",
            system_prompt="You are a helpful assistant.",
            model="gpt-5-nano",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            tools=["tool1"],
            policy=AgentPolicy(max_tool_calls=5, temperature=0.5),
            skills=["skill1"],
            skill_dirs=[Path("/tmp/skills")],
            auto_load_dependencies=False,
            metadata={"key": "value"}
        )
        json_str = config.to_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "my-agent"
        assert parsed["instructions"] == "Be helpful."
        assert parsed["model"] == "gpt-5-nano"
        assert parsed["provider"] == "openai"
        assert parsed["base_url"] == "https://api.openai.com/v1"
        assert parsed["api_key"] == "sk-test"
        assert parsed["tools"] == ["tool1"]
        assert parsed["policy"]["max_tool_calls"] == 5
        assert parsed["skills"] == ["skill1"]
        assert parsed["auto_load_dependencies"] is False
        assert parsed["metadata"] == {"key": "value"}

    def test_to_json_custom_indent(self):
        """Test custom indent level."""
        config = AgentConfig(name="test-agent")
        json_str = config.to_json(indent=4)
        # Should have 4-space indentation
        assert "    " in json_str

    def test_to_json_redact_sensitive(self):
        """Test redaction of sensitive fields."""
        config = AgentConfig(name="test-agent", api_key="secret-key-123")
        json_str = config.to_json(redact_sensitive=True)
        parsed = json.loads(json_str)
        assert parsed["api_key"] == "***REDACTED***"

    def test_roundtrip_from_json_to_json(self):
        """Test roundtrip: from_json(to_json(config))."""
        original = AgentConfig(
            name="test-agent",
            model="gpt-5-nano",
            instructions="Be helpful.",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            skills=["skill1"],
            skill_dirs=[Path("/tmp/skills")],
            auto_load_dependencies=False,
            metadata={"key": "value"}
        )
        json_str = original.to_json()
        restored = AgentConfig.from_json(json_str)
        assert restored.name == original.name
        assert restored.model == original.model
        assert restored.instructions == original.instructions
        assert restored.provider == original.provider
        assert restored.base_url == original.base_url
        assert restored.api_key == original.api_key
        assert restored.skills == original.skills
        assert restored.auto_load_dependencies == original.auto_load_dependencies
        assert restored.metadata == original.metadata


class TestToYaml:
    """Tests for AgentConfig.to_yaml() method."""

    def test_to_yaml_returns_valid_yaml(self):
        """Test that to_yaml returns valid YAML string."""
        config = AgentConfig(name="test-agent", model="gpt-5-nano")
        yaml_str = config.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert parsed["name"] == "test-agent"
        assert parsed["model"] == "gpt-5-nano"

    def test_to_yaml_includes_all_fields(self):
        """Test that to_yaml includes all configuration fields."""
        config = AgentConfig(
            name="my-agent",
            model="gpt-5-nano",
            instructions="Be helpful.",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            skills=["skill1"],
            skill_dirs=[Path("/tmp/skills")],
            auto_load_dependencies=False,
            metadata={"key": "value"}
        )
        yaml_str = config.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert parsed["name"] == "my-agent"
        assert parsed["model"] == "gpt-5-nano"
        assert parsed["skills"] == ["skill1"]
        assert parsed["auto_load_dependencies"] is False

    def test_to_yaml_redact_sensitive(self):
        """Test redaction of sensitive fields."""
        config = AgentConfig(name="test-agent", api_key="secret-key-123")
        yaml_str = config.to_yaml(redact_sensitive=True)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["api_key"] == "***REDACTED***"

    def test_roundtrip_from_yaml_to_yaml(self):
        """Test roundtrip: from_config(to_yaml(config))."""
        original = AgentConfig(
            name="test-agent",
            model="gpt-5-nano",
            instructions="Be helpful.",
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            skills=["skill1"],
            skill_dirs=[Path("/tmp/skills")],
            auto_load_dependencies=False,
            metadata={"key": "value"}
        )
        yaml_str = original.to_yaml()
        # Parse YAML to dict, then use from_config
        parsed = yaml.safe_load(yaml_str)
        restored = AgentConfig.from_config(parsed)
        assert restored.name == original.name
        assert restored.model == original.model
        assert restored.instructions == original.instructions
        assert restored.provider == original.provider
        assert restored.base_url == original.base_url
        assert restored.api_key == original.api_key
        assert restored.skills == original.skills
        assert restored.auto_load_dependencies == original.auto_load_dependencies
        assert restored.metadata == original.metadata


class TestFromJsonFile:
    """Tests for AgentConfig.from_json_file() method."""

    def test_from_json_file_loads_correctly(self):
        """Test loading from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "test-agent", "model": "gpt-5-nano"}, f)
            temp_path = Path(f.name)

        try:
            config = AgentConfig.from_json_file(temp_path)
            assert config.name == "test-agent"
            assert config.model == "gpt-5-nano"
        finally:
            temp_path.unlink()

    def test_from_json_file_handles_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                AgentConfig.from_json_file(temp_path)
        finally:
            temp_path.unlink()


class TestFromYamlFile:
    """Tests for AgentConfig.from_yaml_file() method."""

    def test_from_yaml_file_loads_correctly(self):
        """Test loading from YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"name": "test-agent", "model": "gpt-5-nano"}, f)
            temp_path = Path(f.name)

        try:
            config = AgentConfig.from_yaml_file(temp_path)
            assert config.name == "test-agent"
            assert config.model == "gpt-5-nano"
        finally:
            temp_path.unlink()

    def test_from_yaml_file_handles_invalid_yaml(self):
        """Test that invalid YAML raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                AgentConfig.from_yaml_file(temp_path)
        finally:
            temp_path.unlink()


class TestToJsonFile:
    """Tests for AgentConfig.to_json_file() method."""

    def test_to_json_file_writes_correctly(self):
        """Test writing to JSON file."""
        config = AgentConfig(name="test-agent", model="gpt-5-nano")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            config.to_json_file(temp_path)
            with open(temp_path) as f:
                loaded = json.load(f)
            assert loaded["name"] == "test-agent"
            assert loaded["model"] == "gpt-5-nano"
        finally:
            temp_path.unlink()


class TestToYamlFile:
    """Tests for AgentConfig.to_yaml_file() method."""

    def test_to_yaml_file_writes_correctly(self):
        """Test writing to YAML file."""
        config = AgentConfig(name="test-agent", model="gpt-5-nano")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = Path(f.name)

        try:
            config.to_yaml_file(temp_path)
            with open(temp_path) as f:
                loaded = yaml.safe_load(f)
            assert loaded["name"] == "test-agent"
            assert loaded["model"] == "gpt-5-nano"
        finally:
            temp_path.unlink()


class TestOpenCodeCompatibility:
    """Tests for OpenCode-compatible JSON format."""

    def test_opencode_format_parses_correctly(self):
        """Test parsing OpenCode-style JSON format."""
        json_str = json.dumps({
            "name": "my-agent",
            "instructions": "You are a helpful assistant...",
            "system_prompt": "You are a helpful assistant.",
            "model": "gpt-5-nano",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "tools": ["search_web", "calculate"],
            "policy": {"max_tool_calls": 10, "parallel_tool_calls": True, "temperature": 1.0},
            "skills": ["web-researcher"],
            "skill_dirs": ["/path/to/skills"],
            "auto_load_dependencies": True,
            "metadata": {}
        })
        config = AgentConfig.from_json(json_str)
        assert config.name == "my-agent"
        assert config.instructions == "You are a helpful assistant..."
        assert config.system_prompt == "You are a helpful assistant."
        assert config.model == "gpt-5-nano"
        assert config.provider == "openai"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.api_key == "sk-..."
        assert config.tools == ["search_web", "calculate"]
        assert config.policy.max_tool_calls == 10
        assert config.policy.parallel_tool_calls is True
        assert config.policy.temperature == 1.0
        assert config.skills == ["web-researcher"]
        assert config.skill_dirs == [Path("/path/to/skills")]
        assert config.auto_load_dependencies is True
        assert config.metadata == {}


class TestEnvironmentVariableSubstitution:
    """Tests for environment variable substitution."""

    def test_env_var_substitution_in_json(self):
        """Test that ${VAR_NAME} is replaced with env var value."""
        os.environ["TEST_API_KEY"] = "env-secret-value"
        try:
            json_str = json.dumps({"name": "test-agent", "api_key": "${TEST_API_KEY}"})
            config = AgentConfig.from_json(json_str)
            assert config.api_key == "env-secret-value"
        finally:
            del os.environ["TEST_API_KEY"]

    def test_env_var_substitution_raises_for_unset_var(self):
        """Test that unset environment variable raises error."""
        # Make sure the variable is not set
        if "NONEXISTENT_VAR_12345" in os.environ:
            del os.environ["NONEXISTENT_VAR_12345"]

        json_str = json.dumps({"name": "test-agent", "api_key": "${NONEXISTENT_VAR_12345}"})
        with pytest.raises(ValueError, match="Environment variable 'NONEXISTENT_VAR_12345' is not set"):
            AgentConfig.from_json(json_str)

    def test_env_var_substitution_in_yaml_file(self):
        """Test environment variable substitution in YAML files."""
        os.environ["TEST_YAML_KEY"] = "yaml-secret-value"
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump({"name": "test-agent", "api_key": "${TEST_YAML_KEY}"}, f)
                temp_path = Path(f.name)

            try:
                config = AgentConfig.from_yaml_file(temp_path)
                assert config.api_key == "yaml-secret-value"
            finally:
                temp_path.unlink()
                del os.environ["TEST_YAML_KEY"]
        except Exception:
            if "TEST_YAML_KEY" in os.environ:
                del os.environ["TEST_YAML_KEY"]
            raise

    def test_env_var_substitution_multiple_vars(self):
        """Test substitution of multiple environment variables."""
        os.environ["TEST_API_KEY"] = "api-key-value"
        os.environ["TEST_BASE_URL"] = "https://custom.api.com"
        try:
            json_str = json.dumps({
                "name": "test-agent",
                "api_key": "${TEST_API_KEY}",
                "base_url": "${TEST_BASE_URL}"
            })
            config = AgentConfig.from_json(json_str)
            assert config.api_key == "api-key-value"
            assert config.base_url == "https://custom.api.com"
        finally:
            del os.environ["TEST_API_KEY"]
            del os.environ["TEST_BASE_URL"]


class TestModelDefaultFix:
    """Tests for the model default value fix."""

    def test_from_config_uses_gpt_5_nano_default(self):
        """Test that from_config uses gpt-5-nano as default model."""
        # Empty dict should use gpt-5-nano (matching dataclass default)
        config = AgentConfig.from_config({})
        assert config.model == "gpt-5-nano"

    def test_roundtrip_preserves_model_value(self):
        """Test that roundtrip preserves model value."""
        original = AgentConfig(model="gpt-4o")
        config_dict = original.to_config()
        restored = AgentConfig.from_config(config_dict)
        assert restored.model == "gpt-4o"
