"""HermesConfig dataclass and YAML loader for Hermes agent configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class HermesConfig:
    """Configuration for Hermes agent runs.

    Attributes:
        model: Model name/path (e.g., "gpt-4", "claude-3").
        api_base: API endpoint URL.
        api_key_env: Env var name for API key (not the key itself).
        temperature: Sampling temperature (default: 0.0).
        max_tokens: Max tokens per response (default: 4096).
        timeout: Request timeout in seconds (default: 120).
        cost_per_token: Cost per token in USD for estimating API costs (default: 0.0000025).
        network_host: Whether to use Docker host networking (default: True).
    """

    model: str
    api_base: str
    api_key_env: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 120
    cost_per_token: float = 0.0000025
    network_host: bool = True


_REQUIRED_FIELDS = {"model", "api_base", "api_key_env"}


def load_hermes_config(path: str) -> HermesConfig:
    """Load and validate Hermes configuration from a YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        Populated HermesConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields are missing or have invalid types.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Hermes config not found: {path}")

    with config_path.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Hermes config must be a YAML mapping")

    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"Hermes config missing required fields: {', '.join(sorted(missing))}"
        )

    return HermesConfig(
        model=str(data["model"]),
        api_base=str(data["api_base"]),
        api_key_env=str(data["api_key_env"]),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 4096)),
        timeout=int(data.get("timeout", 120)),
        cost_per_token=float(data.get("cost_per_token", 0.0000025)),
        network_host=bool(data.get("network_host", True)),
    )
