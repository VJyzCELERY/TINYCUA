"""Per-agent configuration loader (YAML + env var resolution)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AgentConfig:
    """Configuration for an agent adapter.

    Attributes:
        name: Agent identifier (e.g., "hermes", "claudecode").
        model: Model name/path.
        api_base: API endpoint URL.
        api_key_env: Env var name for API key.
        docker_image: Docker image tag.
        dockerfile_path: Path to Dockerfile.
        timeout_seconds: Per-task timeout in seconds.
        extra_env: Additional environment variables.
    """

    name: str
    model: str
    api_base: str
    api_key_env: str
    docker_image: str
    dockerfile_path: str
    timeout_seconds: int = 300
    extra_env: dict[str, str] = field(default_factory=dict)


_REQUIRED_FIELDS = {"name", "model", "api_base", "api_key_env", "docker_image"}


def load_config(path: str) -> AgentConfig:
    """Load and validate agent configuration from a YAML file.

    Supports environment variable interpolation using ${VAR_NAME} syntax.

    Args:
        path: Path to the YAML config file.

    Returns:
        Populated AgentConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields are missing or have invalid types.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with config_path.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Config must be a YAML mapping")

    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"Config missing required fields: {', '.join(sorted(missing))}"
        )

    resolved = {}
    for key, value in data.items():
        if isinstance(value, str):
            resolved[key] = _resolve_env_vars(value)
        elif isinstance(value, dict):
            resolved[key] = {
                k: _resolve_env_vars(v) if isinstance(v, str) else v
                for k, v in value.items()
            }
        else:
            resolved[key] = value

    return AgentConfig(
        name=str(resolved["name"]),
        model=str(resolved["model"]),
        api_base=str(resolved["api_base"]),
        api_key_env=str(resolved["api_key_env"]),
        docker_image=str(resolved["docker_image"]),
        dockerfile_path=str(resolved.get("dockerfile_path", "")),
        timeout_seconds=int(resolved.get("timeout_seconds", 300)),
        extra_env=resolved.get("extra_env", {}),
    )


def _resolve_env_vars(value: str) -> str:
    """Resolve ${VAR_NAME} references to environment variable values.

    Args:
        value: String potentially containing ${VAR_NAME} references.

    Returns:
        Resolved string with env var values substituted.
    """
    if "${" not in value:
        return value
    result = value
    for key, val in os.environ.items():
        result = result.replace(f"${{{key}}}", val)
    return result
