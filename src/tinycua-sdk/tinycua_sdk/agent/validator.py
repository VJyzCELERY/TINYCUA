"""Agent configuration validator."""

import re
from dataclasses import dataclass
from enum import Enum

from tinycua_sdk.agent.config import AgentConfig
from tinycua_sdk.core.providers import VALID_PROVIDERS


class SeverityLevel(Enum):
    """Severity level for validation messages."""

    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationError:
    """Represents a validation error or warning."""

    field: str
    message: str
    severity: SeverityLevel


class AgentConfigValidator:
    """Validates agent configurations."""

    KNOWN_PROVIDERS: set[str] = set(VALID_PROVIDERS)
    KNOWN_MODELS: set[str] = {
        "gpt-5-nano",
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "claude-3-5-sonnet",
        "claude-3-opus",
        "gemini-2.0-flash",
    }
    KNOWN_LOOP_TYPES: set[str] = {
        "default",
        "simple",
    }
    TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    def validate(self, config: AgentConfig) -> list[ValidationError]:
        """Validate agent configuration.

        Args:
            config: AgentConfig to validate

        Returns:
            List of validation errors/warnings (empty if valid)
        """
        errors = []

        # Check required fields
        if not config.name or not config.name.strip():
            errors.append(
                ValidationError(
                    field="name",
                    message="Agent name is required and cannot be empty",
                    severity=SeverityLevel.ERROR,
                )
            )

        # Check provider (now inside llm_model)
        provider = config.llm_model.provider if config.llm_model else None
        if provider and provider not in self.KNOWN_PROVIDERS:
            errors.append(
                ValidationError(
                    field="llm_model.provider",
                    message=f"Unknown provider '{provider}'. Known providers: {', '.join(sorted(self.KNOWN_PROVIDERS))}",
                    severity=SeverityLevel.WARNING,
                )
            )

        # Check temperature
        if config.policy and config.policy.temperature > 2.0:
            errors.append(
                ValidationError(
                    field="policy.temperature",
                    message=f"Temperature {config.policy.temperature} is unusually high (max typically 2.0). Consider using a lower value.",
                    severity=SeverityLevel.WARNING,
                )
            )

        # Check loop configuration
        if config.loop:
            loop_type = (
                config.loop.get("type") if isinstance(config.loop, dict) else None
            )
            if loop_type and loop_type not in self.KNOWN_LOOP_TYPES:
                errors.append(
                    ValidationError(
                        field="loop.type",
                        message=f"Unknown loop type '{loop_type}'. Known types: {', '.join(sorted(self.KNOWN_LOOP_TYPES))}",
                        severity=SeverityLevel.WARNING,
                    )
                )

        # Check tool name format
        if config.tools:
            for tool in config.tools:
                tool_name = (
                    tool if isinstance(tool, str) else getattr(tool, "name", None)
                )
                if tool_name and not self.TOOL_NAME_PATTERN.match(tool_name):
                    errors.append(
                        ValidationError(
                            field="tools",
                            message=f"Invalid tool name '{tool_name}'. Tool names should contain only alphanumeric characters, underscores, and hyphens.",
                            severity=SeverityLevel.WARNING,
                        )
                    )

        return errors
