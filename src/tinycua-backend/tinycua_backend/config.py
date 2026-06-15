"""Configuration management for tinycua-backend."""

import threading
import time
from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel


class RunnerConfig(BaseModel):
    """Runner configuration."""

    url: str = "http://localhost:8001"
    token: str = "runner-secret-token"


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "postgresql://user:pass@localhost:5432/tinycua"


class AuthConfig(BaseModel):
    """Authentication configuration."""

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key: str = ""  # Global API key for simple access


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000


class Config(BaseModel):
    """Main configuration."""

    runner: RunnerConfig = RunnerConfig()
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    server: ServerConfig = ServerConfig()

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


class ConfigWatcher:
    """Watch config file for changes and reload."""

    def __init__(self, path: str, callback: Callable[[Config], None]):
        """Initialize the watcher.

        Args:
            path: Path to config file
            callback: Function to call when config changes
        """
        self.path = Path(path)
        self.callback = callback
        self._running = False
        self._config: Config | None = None

    def start(self) -> None:
        """Start watching for config changes."""
        self._running = True
        self._config = Config.load(str(self.path))
        thread = threading.Thread(target=self._watch, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop watching for config changes."""
        self._running = False

    def get_config(self) -> Config:
        """Get current config."""
        if self._config is None:
            self._config = Config.load(str(self.path))
        return self._config

    def _watch(self) -> None:
        """Watch for file changes."""
        if not self.path.exists():
            return

        mtime = self.path.stat().st_mtime
        while self._running:
            time.sleep(1)
            try:
                new_mtime = self.path.stat().st_mtime
            except OSError:
                continue
            if new_mtime != mtime:
                mtime = new_mtime
                try:
                    self._config = Config.load(str(self.path))
                    self.callback(self._config)
                except Exception:
                    pass


_config_watcher: ConfigWatcher | None = None
_config: Config | None = None


def get_config() -> Config:
    """Get the current configuration.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def init_config(
    path: str = ".config.yaml", reload_callback: Callable[[Config], None] | None = None
) -> Config:
    """Initialize configuration with optional hot-reload.

    Args:
        path: Path to config file
        reload_callback: Optional callback when config is reloaded

    Returns:
        Config instance
    """
    global _config_watcher
    global _config

    _config = Config.load(path)

    if reload_callback:
        _config_watcher = ConfigWatcher(path, reload_callback)
        _config_watcher.start()

    return _config
