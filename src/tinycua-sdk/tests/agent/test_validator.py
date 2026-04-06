"""Unit tests for AgentConfigValidator."""

import pytest
from tinycua_sdk.agent.validator import (
    AgentConfigValidator,
    ValidationError,
    SeverityLevel,
)
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy


@pytest.fixture
def validator():
    return AgentConfigValidator()


@pytest.fixture
def valid_config():
    return AgentConfig(
        name="test-agent",
        model="gpt-4o-mini",
        provider="openai",
    )


class TestAgentConfigValidator:
    """Tests for AgentConfigValidator class."""

    def test_valid_config_passes(self, validator, valid_config):
        """Test that valid config passes validation."""
        errors = validator.validate(valid_config)

        # Should have no errors
        assert not any(e.severity == SeverityLevel.ERROR for e in errors)

    def test_missing_name_error(self, validator):
        """Test that missing name raises error."""
        config = AgentConfig(name="")
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert any("name" in msg.lower() for msg in error_messages)
        assert any(e.severity == SeverityLevel.ERROR for e in errors)

    def test_unknown_provider_warning(self, validator, valid_config):
        """Test warning for unknown provider."""
        config = AgentConfig(
            name="test-agent",
            provider="unknown-provider",
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert any("provider" in msg.lower() for msg in error_messages)
        assert any(e.severity == SeverityLevel.WARNING for e in errors)

    def test_high_temperature_warning(self, validator, valid_config):
        """Test warning for temperature > 2.0."""
        config = AgentConfig(
            name="test-agent",
            policy=AgentPolicy(temperature=2.5),
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert any("temperature" in msg.lower() for msg in error_messages)
        assert any(e.severity == SeverityLevel.WARNING for e in errors)

    def test_valid_temperature_no_warning(self, validator, valid_config):
        """Test no warning for valid temperature."""
        config = AgentConfig(
            name="test-agent",
            policy=AgentPolicy(temperature=1.0),
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert not any("temperature" in msg.lower() for msg in error_messages)

    def test_unknown_loop_type_warning(self, validator, valid_config):
        """Test warning for unknown loop type."""
        config = AgentConfig(
            name="test-agent",
            loop={"type": "unknown-loop-type", "max_iterations": 10},
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert any("loop" in msg.lower() for msg in error_messages)
        assert any(e.severity == SeverityLevel.WARNING for e in errors)

    def test_valid_loop_type_no_warning(self, validator, valid_config):
        """Test no warning for valid loop type."""
        config = AgentConfig(
            name="test-agent",
            loop={"type": "default", "max_iterations": 10},
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert not any("loop" in msg.lower() for msg in error_messages)

    def test_invalid_tool_name_warning(self, validator, valid_config):
        """Test warning for invalid tool name format."""
        config = AgentConfig(
            name="test-agent",
            tools=["valid_tool", "invalid tool!", "another@tool"],
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert any("tool" in msg.lower() for msg in error_messages)
        assert any(e.severity == SeverityLevel.WARNING for e in errors)

    def test_valid_tool_name_no_warning(self, validator, valid_config):
        """Test no warning for valid tool name format."""
        config = AgentConfig(
            name="test-agent",
            tools=["search_web", "calculate", "my_tool_123"],
        )
        errors = validator.validate(config)

        error_messages = [e.message for e in errors]
        assert not any("tool" in msg.lower() for msg in error_messages)

    def test_multiple_warnings(self, validator, valid_config):
        """Test multiple warnings are collected."""
        config = AgentConfig(
            name="test-agent",
            provider="unknown",
            policy=AgentPolicy(temperature=3.0),
            loop={"type": "unknown", "max_iterations": 10},
            tools=["invalid tool!"],
        )
        errors = validator.validate(config)

        # Should have multiple warnings
        assert len(errors) >= 3

    def test_validation_error_dataclass(self, validator):
        """Test ValidationError dataclass."""
        error = ValidationError(
            field="test-field",
            message="Test error message",
            severity=SeverityLevel.ERROR,
        )

        assert error.field == "test-field"
        assert error.message == "Test error message"
        assert error.severity == SeverityLevel.ERROR

    def test_severity_level_enum(self, validator):
        """Test SeverityLevel enum values."""
        assert SeverityLevel.ERROR.value == "error"
        assert SeverityLevel.WARNING.value == "warning"
