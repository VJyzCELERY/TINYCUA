"""Configuration management for tinycua-backend."""

import os
import threading
import time
from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel


class RunnerConfig(BaseModel):
    """Runner configuration."""

    url: str = "http://localhost:8001"
    token: str = ""


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "postgresql://user:pass@localhost:5432/tinycua"
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    pool_pre_ping: bool = True


class AuthConfig(BaseModel):
    """Authentication configuration."""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key: str = ""  # Global API key for simple access


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]


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

        config = cls(**data)

        # Override with environment variables
        if os.environ.get("RUNNER_TOKEN"):
            config.runner.token = os.environ["RUNNER_TOKEN"]
        if os.environ.get("JWT_SECRET"):
            config.auth.jwt_secret = os.environ["JWT_SECRET"]
        if os.environ.get("API_KEY"):
            config.auth.api_key = os.environ["API_KEY"]
        if os.environ.get("DATABASE_URL"):
            config.database.url = os.environ["DATABASE_URL"]
        if os.environ.get("DATABASE_POOL_SIZE"):
            config.database.pool_size = int(os.environ["DATABASE_POOL_SIZE"])
        if os.environ.get("DATABASE_MAX_OVERFLOW"):
            config.database.max_overflow = int(os.environ["DATABASE_MAX_OVERFLOW"])

        return config


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
_config_lock = threading.Lock()
_config_watcher_lock = threading.Lock()


def get_config() -> Config:
    """Get the current configuration.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        with _config_lock:
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

    with _config_lock:
        _config = Config.load(path)

    if reload_callback:
        with _config_watcher_lock:
            _config_watcher = ConfigWatcher(path, reload_callback)
            _config_watcher.start()

    return _config
