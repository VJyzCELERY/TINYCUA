"""Configuration module for tinycua-sdk."""

import os
from pathlib import Path
from typing import Any


def _load_env():
    """Load environment variables from .env file if present."""
    try:
        from dotenv import load_dotenv

        # Look for .env in the parent of the module directory (project root)
        module_dir = Path(__file__).parent.parent
        env_path = module_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


_load_env()


class Config:
    """Global configuration for tinycua-sdk."""

    # Backend Configuration
    BACKEND_URL: str = os.getenv("TINYCUA_BACKEND_URL", "http://localhost:8000")
    API_KEY: str = os.getenv("TINYCUA_API_KEY", "")

    # Default Provider Configuration
    PROVIDER: str = os.getenv("TINYCUA_PROVIDER", "lmstudio")
    MODEL: str = os.getenv("TINYCUA_MODEL", "qwen/qwen3.5-9b")
    BASE_URL: str = os.getenv("TINYCUA_BASE_URL", "http://localhost:1234")

    @classmethod
    def from_env(cls) -> dict[str, Any]:
        """Get config as dict for Agent creation."""
        return {
            "provider": cls.PROVIDER,
            "model": cls.MODEL,
            "base_url": cls.BASE_URL,
            "api_key": cls.API_KEY,
        }


# Global config instance
config = Config()


def configure(
    backend_url: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> None:
    """Configure global settings."""
    if backend_url is not None:
        Config.BACKEND_URL = backend_url
    if api_key is not None:
        Config.API_KEY = api_key
    if provider is not None:
        Config.PROVIDER = provider
    if model is not None:
        Config.MODEL = model
    if base_url is not None:
        Config.BASE_URL = base_url
