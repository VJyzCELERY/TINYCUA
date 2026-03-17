"""Runner configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class Config(BaseModel):
    """Runner configuration."""

    runner_token: str = "default-runner-token"
    host: str = "0.0.0.0"
    port: int = 8001

    @classmethod
    def load(cls, path: str = ".config.yaml") -> "Config":
        """Load configuration from YAML file.

        Args:
            path: Path to config file

        Returns:
            Config instance
        """
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)


_config: Config | None = None


def init_config(config_path: str = ".config.yaml") -> Config:
    """Initialize configuration.

    Args:
        config_path: Path to config file

    Returns:
        Config instance
    """
    global _config
    _config = Config.load(config_path)
    return _config


def get_config() -> Config:
    """Get the current configuration.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config.load()
    return _config
